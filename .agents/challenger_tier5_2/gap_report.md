# Adversarial Coverage Audit & Gap Report

This report outlines the gaps, vulnerabilities, and uncovered branches in the test suite and implementation of the Enterprise Ontology Discovery Agent, along with proposed adversarial test cases to address these gaps.

---

## 1. Identified Gaps & Vulnerabilities

### Gap 1: Over-Restrictive Cypher Safety Check (False Positives on Read-Only Queries)
* **File & Line**: `src/nodes.py`, Lines 96-101
* **Observation**: 
  ```python
  if re.search(r"\b(CREATE|MERGE|SET|DELETE|REMOVE|DETACH)\b", cleaned_cypher, re.IGNORECASE):
      print(f"Blocking modifying Cypher query: {cleaned_cypher}")
      return {
          "query_execution_error": "Modifying Cypher operations are blocked.",
          "cypher_retry_count": state.get("cypher_retry_count", 0) + 1
      }
  ```
* **Vulnerability**: This regex performs a simple substring match with word boundaries. If a user issues a search query that compiles into a safe Cypher query containing any of the blocked words as string literals or within comments (e.g., `MATCH (d:Dataset) WHERE d.description CONTAINS "delete logs"`), the query will be falsely blocked, and the retry counter will increment.
* **Risk**: High (Denial of Service for valid read-only searches containing common database-related terms).

### Gap 2: Incomplete Cypher Safety Check (False Negatives on DDL/Administrative Operations)
* **File & Line**: `src/nodes.py`, Lines 96-101
* **Observation**: The safety check only blocks `CREATE`, `MERGE`, `SET`, `DELETE`, `REMOVE`, and `DETACH`.
* **Vulnerability**: It does not block DDL keywords like `DROP` or `ALTER`, nor administrative operations like `STOP DATABASE`. An LLM hallucination or an injection exploit could run `DROP CONSTRAINT unique_domain_name` or `DROP INDEX dataset_description_embeddings` on the database without triggering the safety check.
* **Risk**: Critical (Potential database schema/index destruction).

### Gap 3: Silent Failure of Vector Search Node
* **File & Line**: `src/nodes.py`, Lines 171-173
* **Observation**:
  ```python
  except Exception as e:
      print(f"Vector search execution error: {e}")
      return {"raw_db_results": [], "query_execution_error": str(e)}
  ```
* **Vulnerability**: If `execute_vector_search_node` throws an exception (due to database connection failure or invalid index), it catches the error and returns an empty list `[]` for `raw_db_results` along with `query_execution_error`. However, the workflow immediately transitions to `synthesize_response_node`, which only checks `query_execution_error` if `retry_count >= 3`. Since vector search has no retry mechanism, it proceeds to synthesize a response with empty results, stating "No records found matching criteria" instead of failing or reporting a database connectivity error.
* **Risk**: Medium (Misleading interface; database failures are reported as empty search results).

### Gap 4: Divergent `MockRecord` Iteration Behavior
* **File & Line**: `src/database.py`, Lines 65-66
* **Observation**:
  ```python
  def __iter__(self):
      return iter(self._data.values())
  ```
* **Vulnerability**: A real `neo4j.Record` behaves like a Python mapping, meaning that iterating over it (e.g., `list(record)` or `for key in record`) yields the **keys** of the record, not the values. However, `MockRecord.__iter__` iterates over the **values**. This leads to a behavioral drift between test environments using the mock driver versus environments using the real driver.
* **Risk**: Medium (Integration tests may pass using the mock driver but crash or behave incorrectly in production when keys are expected instead of values).

### Gap 5: Untested Governance metadata / empty owner rule
* **File & Line**: `src/nodes.py`, Lines 199-204 (Rule 2)
* **Observation**: 
  `Rule 2: If a dataset is found but has empty owners or unassigned departments, clearly say: 'Data asset found, but ownership/governance metadata is unassigned.'`
* **Vulnerability**: While this rule is defined in the synthesis prompt, there are zero tests in the suite validating that it is respected or that the synthesis output contains the mandated disclaimer for unowned datasets (such as `Legacy_FOTA_Logs`).
* **Risk**: Low (Undetected regressions in LLM compliance).

---

## 2. Proposed Adversarial Test Cases

We propose the following new test cases to be added to the test suite (e.g., in `tests/test_adversarial_gaps.py` or integrated into existing files) to enforce coverage and verify correct handling of the above failure modes.

### Python Code for Adversarial Tests

```python
import pytest
from unittest.mock import MagicMock, patch
from src.nodes import execute_cypher_node, execute_vector_search_node, synthesize_response_node
from src.database import MockRecord

# =====================================================================
# Gap 1 & 2: Cypher Safety Node Edge Cases
# =====================================================================

def test_cypher_safety_false_positives(initial_state):
    """
    Adversarial Test for Gap 1:
    Verifies that safe Cypher queries containing blocked keywords inside string literals
    or comments are NOT blocked by the safety regex.
    """
    initial_state["generated_cypher"] = (
        "MATCH (d:Dataset) "
        "WHERE d.description CONTAINS 'delete logs' OR d.name = 'create_telemetry' "
        "RETURN d.name AS dataset_name"
    )
    initial_state["cypher_retry_count"] = 0
    
    with patch("src.nodes.get_driver") as mock_get_driver:
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_session.run.return_value = [{"dataset_name": "Vehicle_Telemetry_Gold"}]
        mock_driver.session.return_value.__enter__.return_value = mock_session
        mock_get_driver.return_value = mock_driver
        
        res = execute_cypher_node(initial_state)
        # Assert the query is NOT blocked and execution succeeds
        assert res["query_execution_error"] is None
        assert res["raw_db_results"] == [{"dataset_name": "Vehicle_Telemetry_Gold"}]


def test_cypher_safety_ddl_and_admin_blocked(initial_state):
    """
    Adversarial Test for Gap 2:
    Verifies that destructive DDL or administrative queries like DROP, ALTER,
    and STOP are blocked by the query safety check before reaching the database.
    """
    # Attempting to drop constraints, indexes, or databases
    ddl_queries = [
        "DROP CONSTRAINT unique_domain_name",
        "DROP INDEX dataset_description_embeddings",
        "ALTER TABLE dataset ADD COLUMN test",
        "STOP DATABASE neo4j"
    ]
    
    for query in ddl_queries:
        initial_state["generated_cypher"] = query
        initial_state["cypher_retry_count"] = 0
        
        res = execute_cypher_node(initial_state)
        assert res["query_execution_error"] == "Modifying Cypher operations are blocked.", \
            f"Query failed to block: {query}"


# =====================================================================
# Gap 3: Vector Search Error Handling
# =====================================================================

def test_vector_search_silent_failure(test_client, mock_openai, mock_neo4j):
    """
    Adversarial Test for Gap 3:
    Verifies that database connection errors during vector search are not silently ignored,
    and do not return a misleading 200 OK 'No records found' response.
    """
    # Force Neo4j connectivity failure
    mock_neo4j.should_fail_connectivity = True
    mock_openai.custom_routing = "vector_search"
    
    response = test_client.post("/query", json={"query": "Find datasets related to driving"})
    
    # The API should raise an HTTP 500 error or return execution error details,
    # rather than succeeding with a 200 OK claiming "No records found".
    assert response.status_code == 500 or "execution failed" in response.json().get("detail", "").lower()


# =====================================================================
# Gap 4: Mock Driver Parity
# =====================================================================

def test_mock_record_iteration_parity():
    """
    Adversarial Test for Gap 4:
    Verifies that MockRecord iteration behaves identically to neo4j.Record
    by yielding keys, not values.
    """
    data = {"key1": "value1", "key2": "value2"}
    record = MockRecord(data)
    
    # In standard neo4j.Record (Mapping), iterating over the record yields its keys.
    # E.g., list(record) should be ['key1', 'key2'].
    assert list(record) == ["key1", "key2"]


# =====================================================================
# Gap 5 & 6: Governance Prompt Rule Audits
# =====================================================================

def test_governance_unassigned_disclaimer_prompt(test_client, mock_openai):
    """
    Adversarial Test for Gap 5 & 6:
    Verifies that queries for datasets with missing owner/governance metadata
    inject the correct instructions into the LLM synthesis prompt.
    """
    mock_openai.custom_routing = "graph_cypher"
    mock_openai.custom_generation = "MATCH (d:Dataset {name: 'Legacy_FOTA_Logs'}) RETURN d.name AS dataset_name, null AS owner_name"
    mock_openai.custom_execution = '[{"dataset_name": "Legacy_FOTA_Logs", "owner_name": null}]'
    
    response = test_client.post("/query", json={"query": "Who owns Legacy_FOTA_Logs?"})
    assert response.status_code == 200
    
    # Inspect the prompt passed to the chat completions API during synthesis
    call_args_list = mock_openai.chat.completions.create.call_args_list
    synthesis_prompt = None
    for call_args in call_args_list:
        prompt_content = call_args[1]["messages"][0]["content"]
        if "governance metadata is unassigned" in prompt_content:
            synthesis_prompt = prompt_content
            break
            
    assert synthesis_prompt is not None
    # Verify the specific rule is present in the prompt
    assert "Rule 2: If a dataset is found but has empty owners or unassigned departments" in synthesis_prompt
```
