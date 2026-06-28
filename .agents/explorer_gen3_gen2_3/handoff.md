# Handoff Report: Ontology Discovery Agent Analysis

This handoff details the findings and logic for the read-only investigation of the Enterprise Ontology Discovery Agent.

---

## 1. Observation

### State-Machine Orchestration
- The `StateGraph` is instantiated and compiled in `src/main.py` (lines 24–91).
- The transition routing function `check_execution_status` in `src/main.py` (lines 64–75) checks the retry count constraint:
  ```python
  if error is not None:
      if retry_count < 5:
          return "correct_cypher"
      else:
          return "synthesize_response"
  ```
- The retry counter `cypher_retry_count` is incremented by `+1` in `src/nodes.py` (lines 82, 89, 96, 113) during failures/blocking events in `execute_cypher_node`.

### FastAPI Service
- The FastAPI application is instantiated in `src/main.py` (lines 125–129) and `/query` is defined as a POST endpoint at `src/main.py` (lines 146–188).
- The HTTP Content-Type middleware is defined in `src/main.py` (lines 134–141):
  ```python
  @app.middleware("http")
  async def check_content_type_middleware(request: Request, call_next):
      if request.url.path == "/query" and request.method == "POST":
          content_type = request.headers.get("content-type", "")
          primary_media_type = content_type.split(";")[0].strip() if content_type else ""
          if primary_media_type != "application/json":
              return JSONResponse(status_code=415, content={"detail": "Unsupported Media Type"})
      return await call_next(request)
  ```

### Cypher Write Protection
- User Cypher queries are checked and executed inside `execute_cypher_node` in `src/nodes.py` (lines 75–115).
- Write operations are blocked at lines 92–97:
  ```python
  if re.search(r"\b(CREATE|MERGE|SET|DELETE|REMOVE|DETACH)\b", cleaned_cypher, re.IGNORECASE):
  ```

### Startup Checks & Seeding
- The seeding script is located at `src/seed_data.py` (entry point `main()`, lines 164–221).
- The FastAPI lifespan context manager is at `src/main.py` (lines 95–124).
- Neo4j connectivity is verified by calling `get_driver().verify_connectivity()` (main.py:116) and `driver.verify_connectivity()` (seed_data.py:182).
- NVIDIA NIM connectivity is tested using `nvidia_client.embeddings.create` with a dummy list `["test"]` (main.py:105-110, seed_data.py:171-175).
- Connection establishment logic is implemented in `src/database.py` (lines 52–71). If connection fails, it retries up to 3 times before raising a `ConnectionError`. No mock driver is used for fallback in production.

### Tests
- Test files are located in `tests/conftest.py` (mocks/fixtures), `tests/test_e2e_opaque.py` (Tiers 1, 2, and 4), and `tests/test_neo4j_fallback.py` (Tier 3).

---

## 2. Logic Chain

1. **Self-Correction Limit**: 
   - An execution failure increments `cypher_retry_count` by 1.
   - For `retry_count < 5`, correction routing occurs. If `retry_count` reaches 5, the flow terminates.
   - This translates to:
     - Original attempt fails (`retry_count` becomes 1) -> 1st retry.
     - 1st retry fails (`retry_count` becomes 2) -> 2nd retry.
     - 2nd retry fails (`retry_count` becomes 3) -> 3rd retry.
     - 3rd retry fails (`retry_count` becomes 4) -> 4th retry.
     - 4th retry fails (`retry_count` becomes 5) -> `5 < 5` is False -> Stop (total attempts = 5).
   - This represents exactly **4 retries** max. If the previous limit was 3 retries (original + 3 retries = 4 total attempts), it was implemented as `retry_count < 4`. Changing it to `retry_count < 5` enables a maximum of 4 retries.

2. **FastAPI HTTP Middleware**:
   - The middleware currently extracts `primary_media_type` and compares it to `"application/json"`.
   - MIME/media type parameters can be case-variant depending on the user client (e.g. `Application/JSON`). To ensure correct validation, the check must evaluate `.lower() != "application/json"`.

3. **Cypher Safety**:
   - The boundary regex `\b(CREATE|MERGE|SET|DELETE|REMOVE|DETACH)\b` prevents blocking words containing these strings (e.g. properties like `setting`).
   - However, any query containing a blocked keyword inside a string literal or a comment will trigger a false positive. By stripping single-line comments (`//.*`) and string literals (`".*?"|\'.*?'`) from the comparison string prior to checking, the system can block actual operations without false positives on text parameters.

4. **Failures on Startup/Seeding**:
   - Both `main.py` lifespan and `seed_data.py` `main()` invoke real connections via `get_driver()` (instantiating `get_neo4j_driver()`).
   - `get_neo4j_driver()` contains an explicit `for` loop raising `ConnectionError` on fail, and `lifespan` wraps it to raise `RuntimeError`. No mock object fallback exists in production. Thus, database unreachability will always halt startup.

---

## 3. Caveats

- **Sandbox Constraints**: All verification was performed in CODE_ONLY mode without a live Neo4j database or Nvidia NIM connection. Connectivity assertions are derived from source code analysis and mocked pytest executions.

---

## 4. Conclusion

- **Correction Limit**: Already set to `retry_count < 5` inside `src/main.py:70`, which allows exactly 4 retries. If the intent is to restrict to 3, it should be changed to `< 4`.
- **FastAPI Service**: Middleware is defined in `src/main.py:134-141`. Recommend updating the matching string to use `.lower()` to handle case variation.
- **Cypher Blocking**: Intercepted in `src/nodes.py:92-97`. Recommend stripping comments and string literals prior to checking.
- **Startup Connectivity**: Confirmed correct. Startup fails on unreachability without fallback.
- **Tests**: Highly structured Tier 1-4 mocks and integration tests are present.

---

## 5. Verification Method

1. Run the test command `pytest tests/` in the project root.
2. Verify that `tests/test_e2e_opaque.py` and `tests/test_neo4j_fallback.py` execute successfully.
3. Inspect `src/main.py` line 70, `src/main.py` line 139, `src/nodes.py` line 92, and `src/database.py` line 52 to confirm locations of features.
