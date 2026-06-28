import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Ensure project root is in python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Set up mock environment variables
os.environ["NVIDIA_API_KEY"] = "mock-nvidia-key"
os.environ["NVIDIA_BASE_URL"] = "https://mock.nvidia.api/v1"
os.environ["NEO4J_URI"] = "bolt://localhost:7687"
os.environ["NEO4J_USER"] = "neo4j"
os.environ["NEO4J_PASSWORD"] = "mock-password"
os.environ["CHAT_MODEL"] = "meta/llama-3.1-70b-instruct"
os.environ["EMBEDDING_MODEL"] = "nvidia/nv-embedqa-e5-v5"

# Mock the entire nvidia_client and driver *before* importing anything that triggers startup logic
import openai
import neo4j

class MockOpenAIClient:
    def __init__(self, *args, **kwargs):
        self.base_url = "https://mock.nvidia.api/v1/"
        self.chat = MagicMock()
        self.embeddings = MagicMock()
        
        # Setup defaults
        self.chat.completions.create.side_effect = self.handle_chat
        self.embeddings.create.side_effect = self.handle_embeddings
        
        self.custom_routing = None
        self.custom_generation = None
        self.custom_execution = None
        self.custom_correction = None
        self.custom_synthesis = None
        self.custom_embeddings = None

    def handle_chat(self, model, messages, temperature=0.0, **kwargs):
        prompt = messages[0]["content"]
        if "catalog router" in prompt:
            res = self.custom_routing if self.custom_routing is not None else "graph_cypher"
        elif "Cypher expert" in prompt:
            res = self.custom_generation if self.custom_generation is not None else "```cypher\nMATCH (d:Domain) RETURN d.name AS domain_name\n```"
        elif "debugging compiler" in prompt:
            res = self.custom_correction if self.custom_correction is not None else "```cypher\nMATCH (d:Domain) RETURN d.name AS domain_name\n```"
        elif "catalog assistant" in prompt:
            res = self.custom_synthesis if self.custom_synthesis is not None else "This is a synthesized mock response."
        else:
            res = "Default mock response"
            
        mock_choice = MagicMock()
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

global_mock_openai = MockOpenAIClient()

# Mock OpenAI class
openai.OpenAI = lambda *args, **kwargs: global_mock_openai

# Mock Neo4j driver
class MockNeo4jDriver:
    def __init__(self, *args, **kwargs):
        self.session = MagicMock()
        self.verify_connectivity = MagicMock()
        self.verify_connectivity.return_value = None
        self.close = MagicMock()
        
        # Configure session mock to return entering context manager
        session_mock = MagicMock()
        session_mock.__enter__.return_value = session_mock
        session_mock.run.return_value = []
        self.session.return_value = session_mock

global_mock_driver = MockNeo4jDriver()
neo4j.GraphDatabase.driver = lambda *args, **kwargs: global_mock_driver

# Now import FastAPI App and workflow
from src.main import app, workflow_graph
from src.nodes import execute_cypher_node
from fastapi.testclient import TestClient

class TestOntologyAgentVerification(unittest.TestCase):

    def setUp(self):
        # Reset mock parameters
        global_mock_openai.custom_routing = None
        global_mock_openai.custom_generation = None
        global_mock_openai.custom_execution = None
        global_mock_openai.custom_correction = None
        global_mock_openai.custom_synthesis = None
        global_mock_openai.custom_embeddings = None
        global_mock_openai.chat.completions.create.reset_mock()
        global_mock_openai.embeddings.create.reset_mock()
        global_mock_openai.chat.completions.create.side_effect = global_mock_openai.handle_chat
        global_mock_openai.embeddings.create.side_effect = global_mock_openai.handle_embeddings
        
        # Safely reset session mock
        session_mock = global_mock_driver.session.return_value.__enter__.return_value
        session_mock.run.reset_mock()
        session_mock.run.side_effect = None
        session_mock.run.return_value = []
        global_mock_driver.close.reset_mock()

    def test_max_retry_count_of_4(self):
        """
        Verify that maximum retry count of 4 works correctly.
        An initial attempt plus 4 retries = 5 total attempts.
        On the 5th retry (which would be 6th attempt), it should stop.
        """
        # Configure NVIDIA LLM mock to return a routing decision, then cypher queries
        # Responses sequence:
        # 1. Routing decision -> "graph_cypher"
        # 2. First Cypher generation -> "MATCH (n) RETRUN n" (bad)
        # 3. Correction 1 -> "MATCH (n) RETRUN n" (bad)
        # 4. Correction 2 -> "MATCH (n) RETRUN n" (bad)
        # 5. Correction 3 -> "MATCH (n) RETRUN n" (bad)
        # 6. Correction 4 -> "MATCH (n) RETRUN n" (bad)
        # 7. Synthesis response (after loop termination)
        mock_choices = []
        
        # Routing
        choice_route = MagicMock()
        choice_route.message.content = "graph_cypher"
        mock_choices.append(MagicMock(choices=[choice_route]))
        
        # First Cypher
        choice_cypher = MagicMock()
        choice_cypher.message.content = "```cypher\nMATCH (n) RETRUN n\n```"
        mock_choices.append(MagicMock(choices=[choice_cypher]))
        
        # Corrections (4 retries)
        for _ in range(4):
            choice_corr = MagicMock()
            choice_corr.message.content = "```cypher\nMATCH (n) RETRUN n\n```"
            mock_choices.append(MagicMock(choices=[choice_corr]))
            
        # Synthesis
        choice_synth = MagicMock()
        choice_synth.message.content = "Synthesized failure response"
        mock_choices.append(MagicMock(choices=[choice_synth]))
        
        global_mock_openai.chat.completions.create.side_effect = mock_choices

        # Configure Neo4j driver mock to raise an error upon run
        session_mock = global_mock_driver.session.return_value.__enter__.return_value
        session_mock.run.side_effect = Exception("Neo4j syntax error")

        # Run the workflow
        initial_state = {
            "user_query": "Find datasets",
            "routing_decision": "",
            "schema_metadata": "Mock schema",
            "generated_cypher": None,
            "query_execution_error": None,
            "raw_db_results": [],
            "cypher_retry_count": 0,
            "synthesized_response": ""
        }
        
        final_state = workflow_graph.invoke(initial_state)
        
        # Verify cypher_retry_count in final state is 5 (1 initial + 4 retries)
        print(f"Final cypher retry count: {final_state.get('cypher_retry_count')}")
        self.assertEqual(final_state.get("cypher_retry_count"), 5)
        
        # Verify that mock_session.run was called exactly 5 times (1 initial attempt + 4 retries)
        print(f"Number of database execution attempts: {session_mock.run.call_count}")
        self.assertEqual(session_mock.run.call_count, 5)

    def test_fastapi_content_type_headers(self):
        """
        Verify that FastAPI POST to /query with content types like application/json; charset=utf-8 succeed,
        while text/plain or missing headers fail with 415.
        """
        with TestClient(app) as client:
            with patch.object(workflow_graph, "invoke") as mock_invoke:
                mock_invoke.return_value = {
                    "synthesized_response": "Success Response",
                    "routing_decision": "direct_respond",
                    "generated_cypher": None,
                    "query_execution_error": None,
                    "cypher_retry_count": 0
                }
                
                # 1. Content-Type: application/json -> Should succeed (200)
                res1 = client.post("/query", json={"query": "Hello"}, headers={"Content-Type": "application/json"})
                print(f"application/json status: {res1.status_code}")
                self.assertEqual(res1.status_code, 200)
                
                # 2. Content-Type: application/json; charset=utf-8 -> Should succeed (200)
                res2 = client.post("/query", json={"query": "Hello"}, headers={"Content-Type": "application/json; charset=utf-8"})
                print(f"application/json; charset=utf-8 status: {res2.status_code}")
                self.assertEqual(res2.status_code, 200)
                
                # 3. Content-Type: text/plain -> Should fail with 415
                res3 = client.post("/query", content="query=Hello", headers={"Content-Type": "text/plain"})
                print(f"text/plain status: {res3.status_code}")
                self.assertEqual(res3.status_code, 415)
                self.assertEqual(res3.json(), {"detail": "Unsupported Media Type"})
                
                # 4. Missing Content-Type -> Should fail with 415
                res4 = client.post("/query", content='{"query": "Hello"}', headers={})
                print(f"Missing header status: {res4.status_code}")
                self.assertEqual(res4.status_code, 415)
                self.assertEqual(res4.json(), {"detail": "Unsupported Media Type"})

    def test_cypher_modification_blocks(self):
        """
        Verify that modifying Cypher queries like CREATE (n), MERGE (n), SET n.prop=1, DELETE n, REMOVE n.prop, DETACH DELETE n
        (case-insensitively, e.g. create, Merge) are successfully blocked before execution.
        """
        modifying_queries = [
            "CREATE (n)",
            "MERGE (n)",
            "SET n.prop=1",
            "DELETE n",
            "REMOVE n.prop",
            "DETACH DELETE n",
            "create (n:Person {name: 'Alice'})",
            "Merge (d:Domain {name: 'IT'})",
            "match (n) set n.name = 'Bob'",
            "match (n) delete n",
            "MATCH (n) remove n.email",
            "match (n) detach delete n",
            "MATCH (n) DETACH  DELETE n"
        ]
        
        for q in modifying_queries:
            state = {
                "generated_cypher": q,
                "cypher_retry_count": 0
            }
            res = execute_cypher_node(state)
            print(f"Query: {q} -> Error: {res.get('query_execution_error')}")
            self.assertEqual(res.get("query_execution_error"), "Modifying Cypher operations are blocked.")
            self.assertEqual(res.get("cypher_retry_count"), 1)

        # Test non-modifying operations (should not be blocked)
        safe_queries = [
            "MATCH (n) RETURN n",
            "MATCH (d:Domain) RETURN d.name AS name, d.description AS desc",
            "MATCH (c:Column) WHERE c.name = 'create_date' RETURN c",
            "MATCH (c:Column) WHERE c.name = 'merge_flag' RETURN c",
            "MATCH (c:Column) WHERE c.name = 'set_value' RETURN c",
            "MATCH (c:Column) WHERE c.name = 'deleted_items' RETURN c",
            "MATCH (c:Column) WHERE c.name = 'remove_record' RETURN c",
            "MATCH (c:Column) WHERE c.name = 'detached_state' RETURN c"
        ]

        for q in safe_queries:
            state = {
                "generated_cypher": q,
                "cypher_retry_count": 0
            }
            res = execute_cypher_node(state)
            self.assertNotEqual(res.get("query_execution_error"), "Modifying Cypher operations are blocked.")

if __name__ == "__main__":
    unittest.main()
