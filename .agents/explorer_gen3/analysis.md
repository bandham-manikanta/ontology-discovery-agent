# Codebase Analysis Report

This report presents a detailed analysis of the Enterprise Ontology Discovery Agent codebase based on the updated requirements. It provides file paths, line numbers, exact observations, and actionable proposals for implementation.

---

## 1. Cypher Self-Correction Retry Limit

### Current State
- The self-correction loop retry limit is checked in `src/main.py` at line 70 within the conditional routing function `check_execution_status`:
  ```python
  64: def check_execution_status(state: AgentState) -> str:
  65:     error = state.get("query_execution_error")
  66:     retry_count = state.get("cypher_retry_count", 0)
  67:     if error == "Modifying Cypher operations are blocked.":
  68:         return "synthesize_response"
  69:     if error is not None:
  70:         if retry_count < 4:
  71:             return "correct_cypher"
  72:         else:
  73:             return "synthesize_response"
  74:     else:
  75:         return "synthesize_response"
  ```
- In addition, tests verifying this behavior are in `tests/test_e2e_opaque.py`:
  - Line 262 (comment) and line 265 in `test_retry_tier1_max_retries_exceeded`:
    ```python
    261: def test_retry_tier1_max_retries_exceeded(initial_state):
    262:     # 3 retries max. In main.py: check_execution_status checks if retry_count < 4 (3 retries, 4 total attempts)
    263:     from src.main import check_execution_status
    264:     initial_state["query_execution_error"] = "Syntax error"
    265:     initial_state["cypher_retry_count"] = 4
    266:     
    267:     route = check_execution_status(initial_state)
    268:     assert route == "synthesize_response"
    ```
  - Line 495 (comment) and line 498 in `test_retry_tier2_infinite_loop_prevention`:
    ```python
    494: def test_retry_tier2_infinite_loop_prevention(mock_openai, initial_state):
    495:     # Test that when retry count reaches 4 (3 retries, 4 total attempts), check_execution_status stops the loop
    496:     from src.main import check_execution_status
    497:     initial_state["query_execution_error"] = "Syntax Error"
    498:     initial_state["cypher_retry_count"] = 4
    499:     route = check_execution_status(initial_state)
    500:     assert route == "synthesize_response"
    ```

### How to Update to a Maximum of 4 Retries
To allow a maximum of 4 retries (meaning up to 5 execution attempts in total before giving up):
1. In **`src/main.py`**, change the comparison on line 70 to `< 5`:
   ```python
   # before
   if retry_count < 4:
   # after
   if retry_count < 5:
   ```
2. In **`tests/test_e2e_opaque.py`**, update the retry limit checks in `test_retry_tier1_max_retries_exceeded` and `test_retry_tier2_infinite_loop_prevention` to use `5` as the threshold instead of `4`:
   ```python
   initial_state["cypher_retry_count"] = 5
   ```

---

## 2. FastAPI `/query` Content-Type Middleware

### Current State
- The middleware in `src/main.py` is defined as:
  ```python
  134: @app.middleware("http")
  135: async def check_content_type_middleware(request: Request, call_next):
  136:     if request.url.path == "/query" and request.method == "POST":
  137:         content_type = request.headers.get("content-type", "")
  138:         if "application/json" not in content_type:
  139:             return JSONResponse(status_code=415, content={"detail": "Unsupported Media Type"})
  140:     return await call_next(request)
  ```
- **Vulnerability**: A malicious or malformed request containing `Content-Type: text/plain; application/json` will satisfy `"application/json" in content_type` but is not a valid JSON media type.

### How to Improve Validation
Extract the primary media type before verification by splitting on the parameter separator `;`:
```python
@app.middleware("http")
async def check_content_type_middleware(request: Request, call_next):
    if request.url.path == "/query" and request.method == "POST":
        content_type = request.headers.get("content-type", "")
        # Extract main media type (ignoring parameters like charset)
        media_type = content_type.split(";")[0].strip()
        if media_type != "application/json":
            return JSONResponse(status_code=415, content={"detail": "Unsupported Media Type"})
    return await call_next(request)
```

---

## 3. Cypher Write Blocking Security Policy

### Current State
- Modifying operations are blocked in `src/nodes.py` line 88 using a regex boundary search:
  ```python
  88:     if re.search(r"\b(CREATE|MERGE|SET|DELETE|REMOVE|DETACH|DROP|ALTER|RENAME|GRANT|REVOKE|DENY|STOP|START)\b", cleaned_cypher, re.IGNORECASE):
  89:         print(f"Blocking modifying Cypher query: {cleaned_cypher}")
  90:         return {
  91:             "query_execution_error": "Modifying Cypher operations are blocked.",
  92:             "cypher_retry_count": state.get("cypher_retry_count", 0) + 1
  93:         }
  ```
- **Vulnerability**: Safe queries that contain keywords inside string literals (e.g. `MATCH (d) WHERE d.desc = "You must create a record"`) will trigger the check and get blocked.

### How to Update the Regex Check
Update the regex to block specifically (`CREATE`, `MERGE`, `SET`, `DELETE`, `REMOVE`, `DETACH`) case-insensitively:
```python
    if re.search(r"\b(CREATE|MERGE|SET|DELETE|REMOVE|DETACH)\b", cleaned_cypher, re.IGNORECASE):
```

---

## 4. Seeding Script & Connectivity Verification

### Current State of Connectivity Checks
In `src/seed_data.py` (lines 157-180), startup connectivity checks are performed, but they exit via `sys.exit(1)` rather than raising exceptions:
```python
157: def main():
158:     # 1. Check NVIDIA_API_KEY
159:     if not NVIDIA_API_KEY:
160:         print("Error: NVIDIA_API_KEY environment variable is missing or empty.", file=sys.stderr)
161:         sys.exit(1)
162:         
163:     # 2. Check NVIDIA NIM connectivity
164:     try:
165:         nvidia_client.embeddings.create(
166:             input=["test"],
167:             model=EMBEDDING_MODEL,
168:             extra_body={"input_type": "query"}
169:         )
170:     except Exception as e:
171:         print(f"Error: NVIDIA NIM is inactive/unreachable. Details: {e}", file=sys.stderr)
172:         sys.exit(1)
173:         
174:     # 3. Check Neo4j connectivity
175:     try:
176:         driver = get_driver()
177:         driver.verify_connectivity()
178:     except Exception as e:
179:         print(f"Error: Neo4j is offline. Details: {e}", file=sys.stderr)
180:         sys.exit(1)
```

### Actionable Updates to Prevent Silent Mock Fallbacks and Raise Errors
1. Raise `ValueError` if `NVIDIA_API_KEY` is missing or empty.
2. Raise `RuntimeError` if NVIDIA NIM connectivity check fails.
3. Raise `ConnectionError` if Neo4j connectivity check fails.
```python
def main():
    # 1. Check NVIDIA_API_KEY
    if not NVIDIA_API_KEY:
        raise ValueError("NVIDIA_API_KEY environment variable is missing or empty.")
        
    # 2. Check NVIDIA NIM connectivity
    try:
        nvidia_client.embeddings.create(
            input=["test"],
            model=EMBEDDING_MODEL,
            extra_body={"input_type": "query"}
        )
    except Exception as e:
        raise RuntimeError(f"NVIDIA NIM is inactive/unreachable. Details: {e}")
        
    # 3. Check Neo4j connectivity
    try:
        driver = get_driver()
        driver.verify_connectivity()
    except Exception as e:
        raise ConnectionError(f"Neo4j is offline. Details: {e}")
```

### Verification of Seed Counts
We verified the exact database seed data structures:
- **Datasets** (4 seeded): `Vehicle_Telemetry_Gold`, `Supplier_Invoices_Raw`, `Dealer_Financing_Silver`, `Legacy_FOTA_Logs`.
- **Domains** (3 seeded): `Connected_Vehicle`, `Supply_Chain`, `Finance`.
- **Columns** (7 seeded): `vin`, `latitude`, `speed_mph`, `supplier_id`, `tax_id`, `invoice_amount`, `raw_payload`.
- **Owners** (3 seeded): `Alice Smith`, `Bob Jones`, `Charlie Brown`.

This matches the requirement of exactly: **4 datasets, 3 domains, 7 columns, and 3 owners**.

---

## 5. Programmatic API Verification Tests & Real Integration Setup

### Custom Mock Driver Configuration in `tests/conftest.py`
Currently, the OpenAI client and Neo4j driver are unconditionally mocked using `autouse=True` fixtures in `tests/conftest.py`.
To run actual/real integration tests without falling back to mock drivers, we can use the environment variable `REAL_INTEGRATION=true` to bypass the mocks.

#### Step 1: Conditionally set mock environment variables
In `tests/conftest.py` lines 8-14, wrap the environment variables setup so they do not override real variables in an integration run:
```python
if os.getenv("REAL_INTEGRATION") != "true":
    os.environ["NVIDIA_API_KEY"] = "mock-nvidia-key"
    os.environ["NVIDIA_BASE_URL"] = "https://mock.nvidia.api/v1"
    os.environ["NEO4J_URI"] = "bolt://localhost:7687"
    os.environ["NEO4J_USER"] = "neo4j"
    os.environ["NEO4J_PASSWORD"] = "mock-password"
    os.environ["CHAT_MODEL"] = "meta/llama-3.1-70b-instruct"
    os.environ["EMBEDDING_MODEL"] = "nvidia/nv-embedqa-e5-v5"
```

#### Step 2: Conditionally apply fixtures
Update the fixtures in `tests/conftest.py` to yield immediately if `REAL_INTEGRATION` is active:
```python
@pytest.fixture(autouse=True)
def mock_openai(monkeypatch):
    if os.getenv("REAL_INTEGRATION") == "true":
        yield
        return
    # ... (existing mock implementation)

@pytest.fixture(autouse=True)
def mock_neo4j(monkeypatch):
    if os.getenv("REAL_INTEGRATION") == "true":
        yield
        return
    # ... (existing mock implementation)
```

### Implementing/Updating the 5 API Verification Cases
These test cases should be added to `tests/test_e2e_opaque.py` (or a dedicated integration file). They conditionally construct expectations depending on whether they are running in integration mode.

#### Case 1: Vehicle telematics query
```python
def test_vehicle_telematics_query(test_client, mock_openai):
    if os.getenv("REAL_INTEGRATION") != "true":
        mock_openai.custom_routing = "vector_search"
        mock_openai.custom_synthesis = "Found Vehicle_Telemetry_Gold dataset with real-time vehicle performance logs."
    
    payload = {"query": "Find gold tier datasets talking about vehicle telematics or GPS coordinate streams"}
    response = test_client.post("/query", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "Vehicle_Telemetry_Gold" in data["response"]
    assert data["meta"]["routing_decision"] == "vector_search"
```

#### Case 2: `speed_mph` owner query
```python
def test_speed_mph_owner_query(test_client, mock_openai):
    if os.getenv("REAL_INTEGRATION") != "true":
        mock_openai.custom_routing = "graph_cypher"
        mock_openai.custom_generation = "MATCH (d:Dataset)-[:HAS_COLUMN]->(c:Column {name: 'speed_mph'})-[:OWNED_BY]->(o:Owner) RETURN o.name AS owner_name"
        mock_openai.custom_execution = '[{"owner_name": "Alice Smith"}]'
        mock_openai.custom_synthesis = "The owner of speed_mph is Alice Smith."
        
    payload = {"query": "Who owns the column speed_mph?"}
    response = test_client.post("/query", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "Alice Smith" in data["response"]
    assert data["meta"]["routing_decision"] == "graph_cypher"
```

#### Case 3: Hello! query (direct conversational response)
```python
def test_hello_direct_respond(test_client, mock_openai):
    if os.getenv("REAL_INTEGRATION") != "true":
        mock_openai.custom_routing = "direct_respond"
        mock_openai.custom_synthesis = "Hello! I am the Enterprise Ontology Discovery Assistant. How can I help you today?"
        
    payload = {"query": "Hello!"}
    response = test_client.post("/query", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "Hello" in data["response"] or "greetings" in data["response"].lower()
    assert data["meta"]["routing_decision"] == "direct_respond"
```

#### Case 4: `text/plain` content type failure (status code 415)
```python
def test_text_plain_content_type_failure(test_client):
    # This middleware check acts locally and does not rely on LLM/Neo4j drivers
    response = test_client.post(
        "/query",
        content="{\"query\": \"Hello!\"}",
        headers={"Content-Type": "text/plain"}
    )
    assert response.status_code == 415
    assert response.json() == {"detail": "Unsupported Media Type"}
```

#### Case 5: Blocked modifying Cypher query
```python
def test_blocked_modifying_cypher_query(test_client, mock_openai):
    if os.getenv("REAL_INTEGRATION") != "true":
        mock_openai.custom_routing = "graph_cypher"
        mock_openai.custom_generation = "CREATE (o:Owner {name: 'Eve'})"
        
    payload = {"query": "Please CREATE a new Owner node named Eve in the database"}
    response = test_client.post("/query", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["has_errors"] is True
    assert data["meta"]["compiled_cypher"] is not None
    assert "CREATE" in data["meta"]["compiled_cypher"].upper()
    assert "blocked" in data["response"].lower()
```

---

## 6. Discovered Codebase Inconsistencies & Bugs

During test investigation, we uncovered several bugs in the current codebase that should be resolved:

1. **Test Contamination in `tests/test_e2e_opaque.py`**:
   The test `test_config_tier1_custom_env_loader` modifies the environment variables `CHAT_MODEL` and `EMBEDDING_MODEL` and reloads `src.database`. However, because it reloads while the monkeypatched env vars are still active, `src.database` gets stuck with these custom configurations. This causes subsequent tests like `test_config_tier1_embedding_call_params` to fail because the global model remains `'custom-emb'` instead of returning to default.
   *Recommendation*: Ensure environment variable overrides are removed before reloading the module to revert state.

2. **Positional Arguments Mismatch in `seed_ontology_data`**:
   In `src/seed_data.py` line 68, `seed_ontology_data` is defined with two parameters: `(session, dataset_embeddings)`. However, several test cases in `tests/test_e2e_opaque.py` and `tests/test_neo4j_fallback.py` invoke `seed_ontology_data(session)` with only one argument. This triggers a `TypeError: seed_ontology_data() missing 1 required positional argument: 'dataset_embeddings'`.
   *Recommendation*: Modify the tests to pass a mock dictionary for `dataset_embeddings` or make the second argument optional in the function signature.

3. **Exception Propagation in `route_query_node`**:
   `test_routing_tier1_exception_fallback` asserts that if the OpenAI API call in `route_query_node` fails, the node falls back to `"graph_cypher"`. However, `route_query_node` in `src/nodes.py` does not wrap the call in a try-except block, causing the exception to propagate and fail the test.
   *Recommendation*: Add a try-except block in `route_query_node` to catch exceptions and return `{"routing_decision": "graph_cypher"}`.

4. **Invalid JSON Body Test Failure (`test_fastapi_tier2_invalid_json_body`)**:
   The test posts raw malformed JSON `"{invalid json"` without specifying a `Content-Type` header (which defaults to `text/plain`). It fails because the new content-type check middleware interceptor throws a `415` status code before the payload hits uvicorn parser to throw a `422`.
   *Recommendation*: Provide `headers={"Content-Type": "application/json"}` in the test request so the request bypasses the content-type middleware check and triggers the body validation check.
