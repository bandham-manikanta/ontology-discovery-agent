# E2E Test Analysis and Recommendations Report

## Summary of Findings

1. **FastAPI & LangGraph Architecture**: The application uses FastAPI for the API boundary (`/query` endpoint) and LangGraph to orchestrate a StateGraph with 6 nodes: query routing (`route_query`), Cypher generation (`generate_cypher`), Cypher execution (`execute_cypher`), Cypher correction (`correct_cypher`), vector database search (`execute_vector_search`), and response synthesis (`synthesize_response`).
2. **Neo4j Connectivity Fallback**: In `src/database.py`, the database driver factory tries to establish connection with a real Neo4j database using environment parameters. If connection fails, it falls back to an LLM-simulated `MockNeo4jDriver` that generates Cypher responses and vector similarity scores via NVIDIA NIM chat completions and embeddings APIs.
3. **Missing Test Framework**: The project does not currently have any unit or integration tests, nor does it have `pytest` or related packages installed in `requirements.txt`.
4. **Opaque-Box E2E Testing Plan**: We propose a 4-tier testing hierarchy implemented using `pytest` and `fastapi.testclient.TestClient`. We can simulate offline databases, network timeouts, and mock both Neo4j execution and NVIDIA NIM LLM endpoints to run E2E test suites hermetically (no-API-key required) or in integration mode.

---

## 1. Entry Points Analysis

### FastAPI Server
* **Source Location**: `src/main.py`
* **Entry Point Object**: `app` (FastAPI instance)
* **Start Command**:
  ```powershell
  python -m uvicorn src.main:app --reload --port 8000
  ```
  *(Or `uvicorn src.main:app --reload --port 8000` once the virtual environment is active)*
* **Key Lifecycle Hooks**: The FastAPI instance utilizes an `asynccontextmanager` lifepan function to initialize the Neo4j driver via `get_driver()` on startup and close it via `close_driver()` on shutdown.

### CLI Seeding Script
* **Source Location**: `src/seed_data.py`
* **Purpose**: Idempotently constructs unique constraints, vector search indexes on `(d:Dataset) ON (d.embedding)` with cosine similarity (1024 dimensions), and seeds mock domains, datasets, columns, owners, and dependencies.
* **Start Command**:
  ```powershell
  python src/seed_data.py
  ```

---

## 2. Code Layout and Key Files in `src/`

* **`src/__init__.py`**: Inits the python package.
* **`src/main.py`**: Defines the FastAPI server and standardizes the `/query` payload schema. It compiles the LangGraph StateGraph, registering conditional edges (e.g. routing after query, cypher execution error self-correction routing) and endpoint invocations.
* **`src/database.py`**: Manages environment variables and instantiates the Neo4j driver. Defines the custom `MockNeo4jDriver`, `MockSession`, `MockResult`, and `MockRecord` classes which simulate Neo4j behavior using NVIDIA NIM endpoints when the database is offline.
* **`src/graph_state.py`**: Defines the type definitions of state variables (e.g., `user_query`, `routing_decision`, `generated_cypher`, `query_execution_error`, `raw_db_results`, `cypher_retry_count`, `synthesized_response`) inside the `AgentState` TypedDict.
* **`src/nodes.py`**: Execution nodes for the graph:
  - `route_query_node`: Determines if the request is `vector_search`, `graph_cypher`, or `direct_respond` via chat completions.
  - `generate_cypher_node`: Generates a Cypher query string matching the schema metadata.
  - `execute_cypher_node`: Executes Cypher query against the active Neo4j driver session.
  - `correct_cypher_node`: LLM-based debugging compiler that attempts to resolve syntax/relationship errors reported from failed execution.
  - `execute_vector_search_node`: Fetches embeddings for the query and executes vector node queries using `db.index.vector.queryNodes`.
  - `synthesize_response_node`: Collates results and builds a human-readable markdown response grounded in graph queries.
* **`src/seed_data.py`**: Connects to the driver and runs Cypher commands to build the initial ontology graph schema.

---

## 3. Required Environment Variables and Configuration

The application loads environment configurations using `python-dotenv`. Based on `src/database.py`, the following variables are supported:

| Environment Variable | Default Value | Purpose |
| --- | --- | --- |
| `NEO4J_URI` | `bolt://localhost:7687` | Connection endpoint for the Neo4j instance |
| `NEO4J_USER` | `neo4j` | Username for Neo4j authentication |
| `NEO4J_PASSWORD` | `password123` | Password for Neo4j authentication |
| `NVIDIA_API_KEY` | *(None)* | Required key for authenticating requests to NVIDIA NIM endpoints |
| `NVIDIA_BASE_URL` | `https://integrate.api.nvidia.com/v1` | Root API host for NVIDIA inference |
| `CHAT_MODEL` | `meta/llama-3.1-70b-instruct` | Chat completion model used for routing, cypher generation/correction, and synthesis |
| `EMBEDDING_MODEL` | `nvidia/nv-embedqa-e5-v5` | Model used for document and query vector generation |

---

## 4. Existing Test Directory and Framework

* **Status**: **No existing test framework or test cases**.
* **Dependencies**: The `requirements.txt` file only includes core operational packages (`fastapi`, `uvicorn`, `langchain`, `langgraph`, `neo4j`, `openai`, `pydantic`, `python-dotenv`).
* **Recommendation**: We must add development dependencies to run tests, specifically:
  - `pytest`
  - `pytest-mock`
  - `httpx` (required for testing FastAPI endpoints asynchronously or via TestClient)
  - `pytest-asyncio` (if tests require async helpers)

---

## 5. Opaque-Box E2E Test Suite Recommendations (Tiers 1-4)

Opaque-box testing interacts with the system solely through the `/query` HTTP endpoint. The client supplies a JSON query string and validates:
1. The HTTP response code.
2. The synthesized output structure and keys (`response` and `meta`).
3. Correct behavior under edge cases and error conditions (such as invalid Cypher generation leading to retry loops, or connection dropouts causing driver fallback).

We propose a 4-Tier test suite structure:

```text
tests/
├── conftest.py             # Global pytest fixtures: mock client, mock drivers, test client, env setups
├── test_e2e_opaque.py      # Opaque-box E2E tests covering Tiers 1, 2, and 4
└── test_neo4j_fallback.py  # Unit/Integration tests verifying Tier 3 (connection fallbacks)
```

### Tier 1: Happy Paths
Verify correct end-to-end execution flow when components behave perfectly.
* **Direct Respond**: Verify query "hello" routes to `direct_respond`, triggers no database queries, returns status 200, and returns `routing_decision` == `"direct_respond"`.
* **Vector Search**: Verify a query asking for driving/telematics datasets routes to `vector_search`, triggers cosine similarity comparison, and returns database results.
* **Graph Cypher**: Verify structural inquiries route to `graph_cypher`, compile Cypher, execute, and synthesize responses correctly.

### Tier 2: Error Resilience & Retries
Verify that LangGraph handles and recovers from runtime errors correctly.
* **Self-Correction Success**: Mock `execute_cypher_node` to fail on first run (raising a syntax/invalid syntax exception). Assert that the state machine routes to `correct_cypher`, attempts a corrected query, succeeds on the second execution, and returns `retry_count` == 1 with `has_errors` == `False`.
* **Retry Loop Termination**: Mock execution to fail continuously. Assert that the loop terminates after 3 failed attempts, synthesizes the fallback timeout warning, and returns `retry_count` == 3 with `has_errors` == `True`.

### Tier 3: Neo4j Connectivity Fallback
Test the resilience of the Neo4j driver factory in `src/database.py`.
* **Online Path**: Mock `neo4j.GraphDatabase.driver` to connect successfully. Verify that `get_neo4j_driver()` returns the live driver and calls `verify_connectivity()`.
* **Offline Path**: Mock `neo4j.GraphDatabase.driver` to raise connection errors. Verify that `get_neo4j_driver()` retries 3 times, prints the warning block, and returns an instance of `MockNeo4jDriver`.
* **Mock Driver Capabilities**: Verify that `MockNeo4jDriver` can successfully calculate cosine similarity for vector search, and run Cypher queries by routing to the chat completion endpoint.

### Tier 4: Hermetic E2E (API-Key-Free Offline Execution)
In CI/CD environments, hitting real NVIDIA endpoints is costly and unreliable. We must supply a mock setup that simulates LLM behaviors without making external network calls.
* We accomplish this by mocking `src.database.nvidia_client` with a mock routing handler.
* The mock handler inspects the incoming prompt content to determine the node context (e.g. routing, generation, correction, or synthesis) and returns predefined text or JSON structure responses.

---

## 6. Pytest Implementation Blueprints

Below are complete blueprints for setting up the E2E suite.

### Global Test Configuration: `tests/conftest.py`

This conftest setups:
1. Environment overrides.
2. A mock OpenAI client (`nvidia_client`) that intercept prompts and returns deterministic responses based on search terms.
3. Overrides for the Neo4j global driver.

```python
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

# Mock environment variables before importing main application components
@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "mock_key")
    monkeypatch.setenv("NEO4J_URI", "bolt://mock-host:7687")
    monkeypatch.setenv("NEO4J_USER", "mock_user")
    monkeypatch.setenv("NEO4J_PASSWORD", "mock_password")

@pytest.fixture
def mock_llm_client(monkeypatch):
    """
    Mock the OpenAI client in database.py to route requests locally.
    This replaces real LLM calls with predictable responses.
    """
    mock_client = MagicMock()
    
    # Setup mock completions
    mock_chat = MagicMock()
    mock_client.chat = mock_chat
    mock_chat.completions = MagicMock()
    
    def mock_chat_completions_create(model, messages, temperature=0.0, **kwargs):
        prompt = messages[0]["content"]
        
        # 1. Routing node mock response
        if "Analyze the user query and route it to one of three targets" in prompt:
            decision = "graph_cypher"
            if "hello" in prompt.lower() or "greet" in prompt.lower():
                decision = "direct_respond"
            elif "pattern" in prompt.lower() or "gps" in prompt.lower() or "similar" in prompt.lower():
                decision = "vector_search"
            
            mock_resp = MagicMock()
            mock_choice = MagicMock()
            mock_choice.message = MagicMock(content=decision)
            mock_resp.choices = [mock_choice]
            return mock_resp
            
        # 2. Cypher generation node mock response
        elif "Database Schema" in prompt and "Write a Cypher query" in prompt:
            if "fail_correction" in prompt.lower():
                cypher_query = "MATCH (d:Dataset) WHERE INVALID SYNTAX"
            elif "trigger_retry" in prompt.lower():
                # First run generated syntax error (will trigger correction)
                cypher_query = "MATCH (d:Dataset) WHERE d.name = 'Vehicle_Telemetry_Gold RETURN d"
            else:
                cypher_query = "MATCH (d:Dataset {name: 'Vehicle_Telemetry_Gold'})-[:OWNED_BY]->(o:Owner) RETURN d.name AS dataset_name, o.name AS owner_name"
                
            mock_resp = MagicMock()
            mock_choice = MagicMock()
            mock_choice.message = MagicMock(content=f"```cypher\n{cypher_query}\n```")
            mock_resp.choices = [mock_choice]
            return mock_resp
            
        # 3. Cypher correction node mock response
        elif "debugging compiler" in prompt:
            if "fail_correction" in prompt.lower():
                corrected_cypher = "MATCH (d:Dataset) WHERE STILL INVALID"
            else:
                corrected_cypher = "MATCH (d:Dataset {name: 'Vehicle_Telemetry_Gold'})-[:OWNED_BY]->(o:Owner) RETURN d.name AS dataset_name, o.name AS owner_name"
                
            mock_resp = MagicMock()
            mock_choice = MagicMock()
            mock_choice.message = MagicMock(content=f"```cypher\n{corrected_cypher}\n```")
            mock_resp.choices = [mock_choice]
            return mock_resp
            
        # 4. Synthesize response node mock response
        elif "Synthesize a professional, grounded markdown response" in prompt or "Respond directly to the user query" in prompt:
            if "direct_respond" in prompt.lower() or "greet" in prompt.lower() or "hello" in prompt.lower():
                text = "Hello! I am your enterprise ontology data catalog assistant. How can I help you?"
            elif "Database query execution timeout" in prompt:
                text = "Database query execution timeout/limit exceeded. Self-correction loop broke."
            else:
                text = "Based on catalog search, the owner of **Vehicle_Telemetry_Gold** is **Alice Smith** from Telemetry Platform Engineering."
                
            mock_resp = MagicMock()
            mock_choice = MagicMock()
            mock_choice.message = MagicMock(content=text)
            mock_resp.choices = [mock_choice]
            return mock_resp
            
        raise ValueError(f"Unmatched mock prompt: {prompt}")
        
    mock_chat.completions.create.side_effect = mock_chat_completions_create
    
    # Setup mock embeddings
    mock_embeddings = MagicMock()
    mock_client.embeddings = mock_embeddings
    
    def mock_embeddings_create(input, model, **kwargs):
        mock_resp = MagicMock()
        mock_data = MagicMock()
        mock_data.embedding = [0.05] * 1024
        mock_resp.data = [mock_data]
        return mock_resp
        
    mock_embeddings.create.side_effect = mock_embeddings_create
    
    monkeypatch.setattr("src.database.nvidia_client", mock_client)
    return mock_client

@pytest.fixture
def mock_db_session():
    """Mock session class to simulate Neo4j result sets and queries."""
    session = MagicMock()
    
    def run_side_effect(query, parameters=None):
        cleaned_query = query.upper()
        # Trigger syntax/execution error paths
        if "INVALID" in cleaned_query or "STILL INVALID" in cleaned_query:
            raise Exception("Neo4j syntax compilation error near 'INVALID'")
        elif "RETURN D" in cleaned_query and "VEHICLE_TELEMETRY_GOLD RETURN" in cleaned_query:
            raise Exception("Neo4j token syntax error: missing quote mark")
            
        # Mock Vector index calls
        if "DB.INDEX.VECTOR.QUERYNODES" in cleaned_query:
            return [
                {
                    "dataset_name": "Vehicle_Telemetry_Gold",
                    "tier": "Gold",
                    "description": "Cleaned, real-time vehicle performance streams.",
                    "schema_summary": "vin, latitude, speed_mph",
                    "score": 0.98
                }
            ]
            
        # Mock default Cypher query execution
        return [
            {"dataset_name": "Vehicle_Telemetry_Gold", "owner_name": "Alice Smith"}
        ]
        
    session.run.side_effect = run_side_effect
    return session

@pytest.fixture
def mock_neo4j_driver(mock_db_session, monkeypatch):
    """
    Overrides get_driver() and returns a mock Neo4j driver that uses
    our mock session instance.
    """
    mock_driver = MagicMock()
    mock_driver.session.return_value.__enter__.return_value = mock_db_session
    mock_driver.verify_connectivity.return_value = True
    
    # Override global driver in database.py
    monkeypatch.setattr("src.database._driver", mock_driver)
    
    # Patch get_driver function to avoid reset
    monkeypatch.setattr("src.database.get_driver", lambda: mock_driver)
    
    return mock_driver

@pytest.fixture
def client(mock_llm_client, mock_neo4j_driver):
    """Returns a FastAPI TestClient configured with mocks."""
    from src.main import app
    with TestClient(app) as test_client:
        yield test_client
```

---

### E2E Opaque-Box Test Cases: `tests/test_e2e_opaque.py`

This test suite covers Tiers 1, 2, and 4. It operates on the `/query` endpoint:

```python
import pytest

# ==========================================
# TIER 1: Happy Paths
# ==========================================

def test_e2e_direct_respond(client):
    """Verify greeting routing responds directly without contacting DB."""
    response = client.post("/query", json={"query": "Hello there agent!"})
    assert response.status_code == 200
    data = response.json()
    assert "response" in data
    assert "Hello! I am your enterprise ontology data catalog assistant" in data["response"]
    assert data["meta"]["routing_decision"] == "direct_respond"
    assert data["meta"]["compiled_cypher"] is None
    assert data["meta"]["retry_count"] == 0
    assert data["meta"]["has_errors"] is False

def test_e2e_vector_search(client):
    """Verify conceptual questions trigger a vector similarity search."""
    response = client.post("/query", json={"query": "find datasets similar to GPS patterns"})
    assert response.status_code == 200
    data = response.json()
    assert "response" in data
    assert "Alice Smith" in data["response"]
    assert data["meta"]["routing_decision"] == "vector_search"
    assert data["meta"]["compiled_cypher"] is None
    assert data["meta"]["retry_count"] == 0
    assert data["meta"]["has_errors"] is False

def test_e2e_graph_cypher_happy(client):
    """Verify structural requests generate and execute correct Cypher statements."""
    response = client.post("/query", json={"query": "Who is the owner of Vehicle_Telemetry_Gold?"})
    assert response.status_code == 200
    data = response.json()
    assert "response" in data
    assert "Alice Smith" in data["response"]
    assert data["meta"]["routing_decision"] == "graph_cypher"
    assert "MATCH" in data["meta"]["compiled_cypher"]
    assert data["meta"]["retry_count"] == 0
    assert data["meta"]["has_errors"] is False

# ==========================================
# TIER 2: Resilience and Errors
# ==========================================

def test_e2e_cypher_self_correction_loop_success(client):
    """
    Verify that if a Cypher query fails initially, the correction node
    intervenes to correct syntax and executes successfully on the retry.
    """
    response = client.post("/query", json={"query": "Who is the owner of Vehicle_Telemetry_Gold? (trigger_retry)"})
    assert response.status_code == 200
    data = response.json()
    assert "response" in data
    assert "Alice Smith" in data["response"]
    assert data["meta"]["routing_decision"] == "graph_cypher"
    assert data["meta"]["retry_count"] == 1
    assert data["meta"]["has_errors"] is False  # Loop resolved successfully

def test_e2e_cypher_self_correction_loop_failure(client):
    """
    Verify that if correction repeatedly fails, the engine exits after 3
    retries, and returns the expected self-correction break message.
    """
    response = client.post("/query", json={"query": "Who is the owner? (fail_correction)"})
    assert response.status_code == 200
    data = response.json()
    assert "response" in data
    assert "Self-correction loop broke" in data["response"]
    assert data["meta"]["routing_decision"] == "graph_cypher"
    assert data["meta"]["retry_count"] == 3
    assert data["meta"]["has_errors"] is True
```

---

### Database Connection and Fallback Tests: `tests/test_neo4j_fallback.py`

This test suite covers Tier 3. It checks the driver initialization logic:

```python
import pytest
from unittest.mock import MagicMock, patch
from src.database import get_neo4j_driver, MockNeo4jDriver

# ==========================================
# TIER 3: Driver Connectivity & Fallbacks
# ==========================================

def test_neo4j_online_returns_real_driver():
    """Verify that if verify_connectivity passes, the active driver is returned."""
    mock_driver_instance = MagicMock()
    mock_driver_instance.verify_connectivity.return_value = True
    
    with patch("src.database.GraphDatabase.driver", return_value=mock_driver_instance) as mock_driver_factory:
        driver = get_neo4j_driver(max_retries=2, delay=0.01)
        mock_driver_factory.assert_called_once()
        mock_driver_instance.verify_connectivity.assert_called_once()
        assert driver == mock_driver_instance

def test_neo4j_offline_falls_back_to_mock_driver():
    """Verify that if connection fails, it retries and falls back to MockNeo4jDriver."""
    mock_driver_instance = MagicMock()
    mock_driver_instance.verify_connectivity.side_effect = Exception("Bolt Connection Error")
    
    with patch("src.database.GraphDatabase.driver", return_value=mock_driver_instance) as mock_driver_factory:
        driver = get_neo4j_driver(max_retries=3, delay=0.01)
        
        # Verify retries occurred
        assert mock_driver_factory.call_count >= 1
        assert isinstance(driver, MockNeo4jDriver)
```
