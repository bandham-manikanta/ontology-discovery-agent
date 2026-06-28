import pytest
from unittest.mock import MagicMock, patch
import os

# ==========================================
# TIER 3: CROSS-FEATURE/PAIRWISE INTERACTIONS (>= 6 tests)
# ==========================================

def test_pairwise_fallback_seeding(mock_neo4j):
    """Test 3.1: Connection Fallback + Seeding.
    Ensures that when connection to real Neo4j fails, 
    attempting to get the driver raises a ConnectionError."""
    # Force connectivity failure on real Neo4j driver
    mock_neo4j.should_fail_connectivity = True
    
    from src.database import get_driver
    
    # Verify that get_driver raises ConnectionError
    with pytest.raises(ConnectionError):
        get_driver()

def test_pairwise_fallback_routing(mock_neo4j, mock_openai, initial_state):
    """Test 3.2: Mocked Connection + State-Machine Routing.
    Ensures that under mocked connectivity, the state machine
    nodes (e.g. execute_vector_search_node) execute successfully."""
    mock_neo4j.should_fail_connectivity = False
    mock_openai.custom_routing = "vector_search"
    
    from src.nodes import execute_hybrid_search_node
    
    # Mock the database response to return our telemetry dataset
    d = mock_neo4j.mock_driver_factory("bolt://localhost:7687", None)
    session_mock = d.session.return_value
    session_mock.run.return_value = [
        {"name": "Vehicle_Telemetry_Gold", "dataset_name": "Vehicle_Telemetry_Gold", "tier": "Gold", "description": "Cleaned telemetry", "schema_summary": "vin", "score": 0.9}
    ]
    
    # Apply the mock driver instance to database
    import src.database
    src.database._driver = d
    
    res = execute_hybrid_search_node(initial_state)
    assert res["query_execution_error"] is None
    assert len(res["raw_db_results"]) > 0
    assert res["raw_db_results"][0]["dataset_name"] == "Vehicle_Telemetry_Gold"

def test_pairwise_config_routing(monkeypatch, mock_openai, initial_state):
    """Test 3.3: Env Config + State-Machine Routing.
    Ensures that custom environment configurations (like model name) 
    are properly passed to OpenAI chat completions during the routing decision."""
    monkeypatch.setenv("CHAT_MODEL", "my-custom-router-model")
    import importlib
    import src.database
    import src.nodes
    importlib.reload(src.database)
    importlib.reload(src.nodes)
    
    mock_openai.custom_routing = "graph_cypher"
    from src.nodes import route_query_node
    
    route_query_node(initial_state)
    
    # Verify that the custom model was passed to the OpenAI API call
    kwargs = mock_openai.chat.completions.create.call_args[1]
    assert kwargs["model"] == "my-custom-router-model"
    
    # Revert env
    importlib.reload(src.database)
    importlib.reload(src.nodes)

def test_pairwise_routing_fastapi(test_client, mock_openai):
    """Test 3.4: State-Machine Routing + FastAPI Endpoint.
    Ensures that routing decisions from the state-machine are cleanly integrated 
    and returned in the FastAPI payload response metadata."""
    mock_openai.custom_routing = "vector_search"
    mock_openai.custom_synthesis = "Vector results synthesized"
    
    response = test_client.post("/query", json={"query": "Find telemetry"})
    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["routing_decision"] == "vector_search"
    assert data["response"] == "Vector results synthesized"

def test_pairwise_correction_flow(mock_neo4j, mock_openai, initial_state):
    """Test 3.5: Cypher Correction + Mocked Execution.
    Ensures that when execute_cypher fails, the correct_cypher node runs 
    and the corrected query successfully executes."""
    mock_neo4j.should_fail_connectivity = False
    
    from src.nodes import execute_cypher_node, correct_cypher_node
    
    d = mock_neo4j.mock_driver_factory("bolt://localhost:7687", None)
    session_mock = d.session.return_value
    
    # Force a syntax error exception on the first call
    session_mock.run.side_effect = [
        Exception("Neo4j Cypher syntax/runtime error: Syntax error near RETRUN"),
        [{"domain_name": "Connected_Vehicle"}] # Success on second call
    ]
    
    import src.database
    src.database._driver = d
    
    # 1. Execute a bad query which fails
    initial_state["generated_cypher"] = "MATCH (n) RETRUN n"
    initial_state["cypher_retry_count"] = 0
    
    res1 = execute_cypher_node(initial_state)
    assert res1["query_execution_error"] is not None
    initial_state["query_execution_error"] = res1["query_execution_error"]
    initial_state["cypher_retry_count"] = res1.get("cypher_retry_count", 1)
    
    # 2. Run correct_cypher node to fix it
    mock_openai.custom_correction = "```cypher\nMATCH (n) RETURN n\n```"
    res2 = correct_cypher_node(initial_state)
    assert res2["generated_cypher"] == "```cypher\nMATCH (n) RETURN n\n```"
    initial_state["generated_cypher"] = res2["generated_cypher"]
    initial_state["query_execution_error"] = None
    
    # 3. Re-run execute node with corrected query (now succeeds)
    res3 = execute_cypher_node(initial_state)
    assert res3["query_execution_error"] is None
    assert len(res3["raw_db_results"]) == 1

def test_pairwise_vectorsearch_embeddings(mock_neo4j, mock_openai, initial_state):
    """Test 3.6: Verify Vector Search uses correct embeddings model."""
    mock_neo4j.should_fail_connectivity = False
    mock_openai.custom_embeddings = [0.1] * 1024
    
    from src.nodes import execute_hybrid_search_node
    
    d = mock_neo4j.mock_driver_factory("bolt://localhost:7687", None)
    session_mock = d.session.return_value
    session_mock.run.return_value = []
    
    import src.database
    src.database._driver = d
    
    res = execute_hybrid_search_node(initial_state)
    assert res["query_execution_error"] is None
    # Verify that embeddings create was called
    assert mock_openai.embeddings.create.called

def test_pairwise_seeding_vectorsearch():
    """Test 3.7: Seeding execution with mocked driver.
    Verifies that setup_constraints_and_indexes and seed_ontology_data
    run their Cypher commands on the driver session."""
    from src.seed_data import setup_constraints_and_indexes, seed_ontology_data
    
    mock_session = MagicMock()
    setup_constraints_and_indexes(mock_session)
    assert mock_session.run.call_count == 6
    
    mock_session.reset_mock()
    seed_ontology_data(mock_session)
    assert mock_session.run.call_count >= 10

def test_pairwise_cypher_safety_check(initial_state):
    """Test 3.7: Cypher Write Operations Safety.
    Verifies that modify/destructive queries are blocked, while safe queries can execute."""
    from src.nodes import execute_cypher_node
    
    # Mock driver to prevent actual connection attempts
    mock_driver = MagicMock()
    mock_session = MagicMock()
    mock_driver.session.return_value = mock_session
    mock_session.__enter__.return_value = mock_session
    
    # 1. Block CREATE
    initial_state["generated_cypher"] = "CREATE (n:Test {name: 'test'})"
    initial_state["cypher_retry_count"] = 0
    with patch("src.nodes.get_driver", return_value=mock_driver):
        res = execute_cypher_node(initial_state)
    assert res["query_execution_error"] == "Modifying Cypher operations are blocked."
    assert res["cypher_retry_count"] == 1
    
    # 2. Block MERGE
    initial_state["generated_cypher"] = "MERGE (d:Domain {name: 'domain'})"
    initial_state["cypher_retry_count"] = 0
    with patch("src.nodes.get_driver", return_value=mock_driver):
        res = execute_cypher_node(initial_state)
    assert res["query_execution_error"] == "Modifying Cypher operations are blocked."
    assert res["cypher_retry_count"] == 1
    
    # 3. Block SET
    initial_state["generated_cypher"] = "MATCH (d:Domain) SET d.name = 'change'"
    initial_state["cypher_retry_count"] = 1
    with patch("src.nodes.get_driver", return_value=mock_driver):
        res = execute_cypher_node(initial_state)
    assert res["query_execution_error"] == "Modifying Cypher operations are blocked."
    assert res["cypher_retry_count"] == 2
    
    # 4. Block DELETE
    initial_state["generated_cypher"] = "MATCH (d:Domain) DELETE d"
    initial_state["cypher_retry_count"] = 2
    with patch("src.nodes.get_driver", return_value=mock_driver):
        res = execute_cypher_node(initial_state)
    assert res["query_execution_error"] == "Modifying Cypher operations are blocked."
    assert res["cypher_retry_count"] == 3
    
    # 5. Block DETACH DELETE
    initial_state["generated_cypher"] = "MATCH (d:Domain) DETACH DELETE d"
    initial_state["cypher_retry_count"] = 0
    with patch("src.nodes.get_driver", return_value=mock_driver):
        res = execute_cypher_node(initial_state)
    assert res["query_execution_error"] == "Modifying Cypher operations are blocked."
    
    # 6. Block REMOVE
    initial_state["generated_cypher"] = "MATCH (d:Domain) REMOVE d.property"
    initial_state["cypher_retry_count"] = 0
    with patch("src.nodes.get_driver", return_value=mock_driver):
        res = execute_cypher_node(initial_state)
    assert res["query_execution_error"] == "Modifying Cypher operations are blocked."

    # 7. Do not block a query that just contains words starting/ending with keywords but not as boundaries
    # E.g., returning properties like "setting" or "deleted"
    initial_state["generated_cypher"] = "MATCH (d:Domain) RETURN d.setting AS setting, d.deleted AS deleted"
    initial_state["cypher_retry_count"] = 0
    with patch("src.nodes.get_driver", return_value=mock_driver):
        res = execute_cypher_node(initial_state)
    # It should not fail with the "blocked" query execution error.
    assert res["query_execution_error"] != "Modifying Cypher operations are blocked."
