# Codebase Analysis Report: Ontology Discovery Agent

This report documents the architectural structure and implementation details of the Enterprise Ontology Discovery Engine codebase, specifically addressing the graph orchestration, service middlewares, query validation/protection, startup checks, and test configurations.

---

## 1. State-Machine Orchestration

### LangGraph StateGraph Definition
The LangGraph workflow state machine is defined in **`src/main.py`** (lines 24–91):
- **Graph Initialization:** `workflow = StateGraph(AgentState)` uses the `AgentState` TypedDict defined in `src/graph_state.py` to maintain graph memory.
- **Node Registration:** The following nodes are registered from `src/nodes.py`:
  - `route_query` -> `route_query_node`
  - `generate_cypher` -> `generate_cypher_node`
  - `execute_cypher` -> `execute_cypher_node`
  - `correct_cypher` -> `correct_cypher_node`
  - `execute_vector_search` -> `execute_vector_search_node`
  - `synthesize_response` -> `synthesize_response_node`
- **Transitions and Edges:**
  - **Entrypoint:** `workflow.set_entry_point("route_query")`
  - **Routing Conditional Edge:** Maps `route_query` to `execute_vector_search`, `generate_cypher`, or `synthesize_response` based on the LLM routing decision (`route_after_query`).
  - **Direct Edges:** `execute_vector_search` -> `synthesize_response` and `generate_cypher` -> `execute_cypher`.
  - **Self-Correction Loop Edge:** A conditional edge is defined from `execute_cypher` using the helper `check_execution_status`. If a query fails execution, the graph loops back to `correct_cypher` and then executes the corrected Cypher again (`correct_cypher` -> `execute_cypher`).
  - **Exit Edge:** `synthesize_response` -> `END`.

### Self-Correction Loop Limit & Retries
The self-correction loop limit is implemented in **`src/main.py`** inside the `check_execution_status` helper function:

```python
def check_execution_status(state: AgentState) -> str:
    error = state.get("query_execution_error")
    retry_count = state.get("cypher_retry_count", 0)
    if error == "Modifying Cypher operations are blocked.":
        return "synthesize_response"
    if error is not None:
        if retry_count < 5:
            return "correct_cypher"
        else:
            return "synthesize_response"
    else:
        return "synthesize_response"
```

#### Detailed Logic & State Transitions:
1. **Initial Execution:** The graph enters `execute_cypher`. If execution fails (either due to database syntax errors or safety block), the `execute_cypher_node` function increments the state counter: `cypher_retry_count = cypher_retry_count + 1` (starting from 0, it becomes 1 on first failure).
2. **First Evaluated Transition:** `check_execution_status` reads `cypher_retry_count = 1`. Since `1 < 5`, it transitions to `correct_cypher` (Retry 1).
3. **Subsequent Corrections:**
   - Failed Retry 1 (Correction Cycle 1) increments count to 2. Checked: `2 < 5` -> route to `correct_cypher` (Retry 2).
   - Failed Retry 2 (Correction Cycle 2) increments count to 3. Checked: `3 < 5` -> route to `correct_cypher` (Retry 3).
   - Failed Retry 3 (Correction Cycle 3) increments count to 4. Checked: `4 < 5` -> route to `correct_cypher` (Retry 4).
   - Failed Retry 4 (Correction Cycle 4) increments count to 5. Checked: `5 < 5` is False -> route to `synthesize_response`.
4. **Current Limit:** Thus, the check `retry_count < 5` allows **4 retries** (attempts to correct), resulting in a maximum of 5 total database execution attempts.
5. **Updating to a Maximum of 4 Retries:** If the codebase previously had a limit of 3 retries (which would be checked via `retry_count < 4`), the current code has already been updated to `retry_count < 5`, which allows exactly **4 retries**.
   - To configure it to a maximum of **N retries**, the conditional check should be `retry_count < (N + 1)`.

---

## 2. FastAPI Service

### App Definition and Endpoints
The FastAPI service is defined in **`src/main.py`**:
- **Application Init:** `app = FastAPI(...)` (lines 125–129) includes the setup of the lifespans (`lifespan=lifespan`).
- **Endpoint:** `@app.post("/query")` (lines 146–187) accepts `QueryPayload`, compiles the initial graph state, and invokes the LangGraph `workflow_graph.invoke(initial_state)`.

### HTTP Middleware for Content-Type Validation
An HTTP middleware to validate `Content-Type` headers for POST requests to `/query` is already implemented in **`src/main.py`** (lines 134–141):

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

#### Middleware Analysis:
- **Operation:** For any POST request destined for `/query`, it checks the header.
- **Robustness:** Splitting by `;` ensures that compound media types (e.g., `application/json; charset=utf-8`) are matched correctly.
- **Response:** If missing or incorrect, it bypasses the endpoint and returns a `415 Unsupported Media Type` status code with JSON body `{"detail": "Unsupported Media Type"}`.
- **Edge Cases:** If FastAPI handles routing dynamically, a request to `/query/` (with trailing slash) might bypass this middleware but still match the route due to FastAPI's redirect behavior. A more robust path check is `request.url.path.rstrip("/") == "/query"`.

---

## 3. Cypher Write Protection

### Execution & Safety Compilation
Cypher queries generated by the LLM are cleaned and intercepted in **`src/nodes.py`** inside the `execute_cypher_node` function (lines 75–115).

### Interception & Regex Boundary Checks
The interception and validation are implemented at line 92 using a case-insensitive regular expression search:

```python
if re.search(r"\b(CREATE|MERGE|SET|DELETE|REMOVE|DETACH)\b", cleaned_cypher, re.IGNORECASE):
    print(f"Blocking modifying Cypher query: {cleaned_cypher}")
    return {
        "query_execution_error": "Modifying Cypher operations are blocked.",
        "cypher_retry_count": state.get("cypher_retry_count", 0) + 1
    }
```

#### Rationale & Technical Details:
- **Case-Insensitivity:** Enforced using the flag `re.IGNORECASE` (or `re.I`), which blocks variations like `create`, `Merge`, `DELETE`, etc.
- **Regex Boundary Checks:** The boundary anchors `\b` prevent false positives when safe query terms contain the keywords as substrings (e.g., aliases or variables like `dataset_deleted` or properties like `setting`).
- **Short-circuiting:** When a destructive query is identified, the node immediately short-circuits, registers the safety block error, increments the retry count, and prevents passing the query to the driver. The graph then evaluates the error in `check_execution_status`, detects the exact block message, and routes directly to response synthesis, bypasses correction, failing fast.

#### Limitations of Regex Protection:
1. **False Positives in Comments:** If the generated Cypher includes a comment containing a blocked word (e.g. `// Need to CREATE domain lookup`), it will be blocked.
2. **False Positives in Literals:** If the query searches for a string literal matching a blocked word (e.g. `MATCH (c:Column) WHERE c.description = "SET value"`), it will be blocked.
3. **Alternative Suggestion:** A safer parser-based AST analysis (e.g. using `openCypher` or python cypher parser libraries) would be more robust for production, though the regex boundary check is standard for simple heuristic filtering.

---

## 4. Startup Checks & Seeding

### Seeding Script and FastAPI Startup Lifespan Locations
- **Database Seeding Script:** **`src/seed_data.py`**
- **FastAPI Startup Lifespan:** **`src/main.py`** (async context manager `lifespan` registered on lines 95–124).

### Connectivity Verification Logic

| Component | Seeding Script (`src/seed_data.py`) | FastAPI Lifespan (`src/main.py`) |
|---|---|---|
| **NVIDIA API Key Check** | `if not NVIDIA_API_KEY: raise ValueError(...)` (Line 166) | `if not NVIDIA_API_KEY: raise ValueError(...)` (Line 101) |
| **NVIDIA NIM Embedding Verification** | Calls `nvidia_client.embeddings.create` with input `"test"` and `EMBEDDING_MODEL` inside a `try...except` block. Raises `RuntimeError` on failure (Lines 170–177). | Calls `nvidia_client.embeddings.create` with input `"test"` and `EMBEDDING_MODEL` inside a `try...except` block. Raises `RuntimeError` on failure (Lines 105–112). |
| **Neo4j Connectivity Verification** | Calls `get_driver()` and performs `verify_connectivity()`. Raises `ConnectionError` on failure (Lines 180–184). | Calls `get_driver().verify_connectivity()`. Raises `RuntimeError` on failure (Lines 115–118). |

### Fallback Analysis
- **No Mock Fallback:** In production (outside of Pytest runs), `src/database.py` contains **no mock driver fallback**. Both `get_neo4j_driver()` and `get_driver()` attempt to instantiate a real driver connecting via the URI `NEO4J_URI`.
- **Failing Fast:** If the Neo4j instance or NVIDIA NIM service is offline, the startup lifespan and seeding script immediately raise `RuntimeError` or `ConnectionError`, terminating execution and preventing the application from starting in an unhealthy state.
- **Test Context Mocks:** Mocking is applied exclusively during tests. In `tests/conftest.py`, Pytest fixtures intercept `GraphDatabase.driver` and replace the global `nvidia_client` reference with `MockOpenAIClient` if `REAL_INTEGRATION` is not set to `true`.

---

## 5. Test Structure & Organization

The project contains a test suite categorized into levels of abstraction:
- **Test Files Location:**
  - `tests/conftest.py` — Shared configurations and mocks.
  - `tests/test_e2e_opaque.py` — Focuses on feature-level and end-to-end testing.
  - `tests/test_neo4j_fallback.py` — Focuses on pairwise integration and connection fallback behavior.

### Testing Architecture
1. **Mocking & Isolation:** The test suite utilizes pytest fixtures in `conftest.py` to completely decouple the tests from external systems:
   - `mock_openai` intercepts calls to chat completions and embeddings, mocking the responses.
   - `mock_neo4j` mocks `neo4j.GraphDatabase.driver` to return mock sessions, preventing connection attempts to a real Neo4j container unless integration testing is active.
   - `mock_sleep` speeds up execution of fallback and retry tests by bypassing delay timers.
2. **Test Categories (Tiers):**
   - **Tier 1 (Feature Coverage):** Tests core functionality like routing, database connection fallback limits, env configs, seeding mock commands, and basic loop count increments.
   - **Tier 2 (Boundary & Corner Cases):** Tests empty inputs, long payloads, media type missing header responses, and invalid configurations.
   - **Tier 3 (Cross-Feature/Pairwise):** Validates combinations of components, such as connection fallback + state machine routing, database schema seeding + vector index initialization.
   - **Tier 4 (Real-World Scenarios):** Full execution path tests (e.g. telemetry lookup, owner retrieval, greetings, self-correction flow success, PII governance warnings).
   - **Adversarial / Integration:** Confirms safety policies (e.g., blocking DDL, handling prompt injections).
