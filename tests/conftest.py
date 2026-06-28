import os
import pytest
import sys
from unittest.mock import MagicMock
import httpx

# Force mock environment variables before any src imports
if os.environ.get("REAL_INTEGRATION") != "true":
    os.environ["NVIDIA_API_KEY"] = "mock-nvidia-key"
    os.environ["NVIDIA_BASE_URL"] = "https://mock.nvidia.api/v1"
    os.environ["NEO4J_URI"] = "bolt://localhost:7687"
    os.environ["NEO4J_USER"] = "neo4j"
    os.environ["NEO4J_PASSWORD"] = "mock-password"
    os.environ["CHAT_MODEL"] = "meta/llama-3.1-70b-instruct"
    os.environ["EMBEDDING_MODEL"] = "nvidia/nv-embedqa-e5-v5"

# Ensure the project root is in the path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Mock OpenAI client classes before importing src
from openai import OpenAI
import neo4j

class MockOpenAIClient:
    def __init__(self, *args, **kwargs):
        self.base_url = httpx.URL("https://mock.nvidia.api/v1/")
        self.chat = MagicMock()
        self.embeddings = MagicMock()
        self.custom_routing = None
        self.custom_generation = None
        self.custom_execution = None
        self.custom_correction = None
        self.custom_synthesis = None
        self.custom_embeddings = None
        
        # Configure the MagicMock completions and embeddings to route through our handler
        self.chat.completions.create.side_effect = self.handle_chat
        self.embeddings.create.side_effect = self.handle_embeddings
        
    def handle_chat(self, model, messages, temperature=0.0, **kwargs):
        prompt = messages[0]["content"]
        
        # Check prompt type
        if "catalog router" in prompt:
            res = self.custom_routing if self.custom_routing is not None else "graph_cypher"
        elif "Cypher expert" in prompt:
            res = self.custom_generation if self.custom_generation is not None else "```cypher\nMATCH (d:Domain) RETURN d.name AS domain_name\n```"
        elif "Cypher Execution engine" in prompt:
            if self.custom_execution is not None:
                res = self.custom_execution
            else:
                res = '[{"domain_name": "Connected_Vehicle"}]'
        elif "debugging compiler" in prompt:
            res = self.custom_correction if self.custom_correction is not None else "```cypher\nMATCH (d:Domain) RETURN d.name AS domain_name\n```"
        elif "catalog assistant" in prompt:
            res = self.custom_synthesis if self.custom_synthesis is not None else "This is a synthesized mock response."
        else:
            res = "Default mock response"
            
        mock_choice = MagicMock()
        mock_choice.message = MagicMock()
        mock_choice.message.content = res
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        return mock_response
        
    def handle_embeddings(self, input, model, **kwargs):
        vector = self.custom_embeddings or ([0.1] * 1024)
        mock_data = MagicMock()
        mock_data.embedding = vector
        mock_response = MagicMock()
        mock_response.data = [mock_data]
        return mock_response

# Create a global mock instance
global_mock_openai = MockOpenAIClient()

# Pytest fixtures
@pytest.fixture(autouse=True)
def mock_sleep(monkeypatch):
    """Bypasses time.sleep to speed up fallback/retry tests."""
    if os.environ.get("REAL_INTEGRATION") != "true":
        monkeypatch.setattr("time.sleep", lambda s: None)

@pytest.fixture(autouse=True)
def reset_global_driver():
    """Ensures each test gets a clean Neo4j driver state."""
    import src.database
    src.database.close_driver()
    yield
    src.database.close_driver()

@pytest.fixture(autouse=True)
def mock_openai(monkeypatch):
    """Allows test cases to customize OpenAI chat and embedding responses."""
    if os.environ.get("REAL_INTEGRATION") == "true":
        class DummyMockOpenAI:
            def __init__(self):
                self.chat = MagicMock()
                self.embeddings = MagicMock()
                self.custom_routing = None
                self.custom_generation = None
                self.custom_execution = None
                self.custom_correction = None
                self.custom_synthesis = None
                self.custom_embeddings = None
        return DummyMockOpenAI()

    # Reset custom response properties
    global_mock_openai.custom_routing = None
    global_mock_openai.custom_generation = None
    global_mock_openai.custom_execution = None
    global_mock_openai.custom_correction = None
    global_mock_openai.custom_synthesis = None
    global_mock_openai.custom_embeddings = None
    
    # Reset call counts and side_effects
    global_mock_openai.chat.completions.create.reset_mock()
    global_mock_openai.embeddings.create.reset_mock()
    global_mock_openai.chat.completions.create.side_effect = global_mock_openai.handle_chat
    global_mock_openai.embeddings.create.side_effect = global_mock_openai.handle_embeddings
    
    # Mock OpenAI class in openai module
    monkeypatch.setattr("openai.OpenAI", lambda *args, **kwargs: global_mock_openai)
    
    # Apply monkeypatch to existing references
    monkeypatch.setattr("src.database.nvidia_client", global_mock_openai)
    monkeypatch.setattr("src.nodes.nvidia_client", global_mock_openai)
    return global_mock_openai

@pytest.fixture(autouse=True)
def mock_neo4j(monkeypatch):
    """Provides a controller for mocking Neo4j driver connection behavior."""
    if os.environ.get("REAL_INTEGRATION") == "true":
        class DummyMockNeo4j:
            def __init__(self):
                self.should_fail_connectivity = False
                self.fail_attempts = 0
                self.current_attempts = 0
                self.driver_instances = []
        return DummyMockNeo4j()

    class MockDriverController:
        def __init__(self):
            self.should_fail_connectivity = False
            self.fail_attempts = 0
            self.current_attempts = 0
            self.driver_instances = []
            
        def mock_driver_factory(self, uri, auth):
            self.current_attempts += 1
            if self.should_fail_connectivity or self.current_attempts <= self.fail_attempts:
                d = MagicMock()
                d.verify_connectivity.side_effect = Exception("Connection failed")
                self.driver_instances.append(d)
                return d
            else:
                d = MagicMock()
                # Mock session
                session_mock = MagicMock()
                session_mock.__enter__.return_value = session_mock
                
                # Make session run return records
                records_mock = MagicMock()
                session_mock.run.return_value = records_mock
                
                d.session.return_value = session_mock
                d.verify_connectivity.return_value = None
                self.driver_instances.append(d)
                return d

    controller = MockDriverController()
    monkeypatch.setattr(neo4j.GraphDatabase, "driver", controller.mock_driver_factory)
    return controller

@pytest.fixture
def test_client():
    """Provides a FastAPI test client."""
    from fastapi.testclient import TestClient
    from src.main import app
    return TestClient(app)

@pytest.fixture
def initial_state():
    """Provides a default initial AgentState dictionary."""
    return {
        "user_query": "hello",
        "routing_decision": "",
        "schema_metadata": "Mock schema metadata",
        "generated_cypher": None,
        "query_execution_error": None,
        "raw_db_results": [],
        "cypher_retry_count": 0,
        "synthesized_response": ""
    }
