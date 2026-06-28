# Task: Implement Tier 5 Hardening & Fix Gaps

## Gaps to Fix

1. **Administrative and Schema-Modifying Cypher Bypass (Critical)**:
   In `src/nodes.py` (`execute_cypher_node`), update the block regex to:
   `re.search(r"\b(CREATE|MERGE|SET|DELETE|REMOVE|DETACH|DROP|ALTER|RENAME|GRANT|REVOKE|DENY|STOP|START)\b", cleaned_cypher, re.IGNORECASE)`
   This will block administrative DDL/DCL queries from reaching the database.

2. **Non-String `generated_cypher` State Crashes**:
   In `src/nodes.py` (`execute_cypher_node`), check if `generated_cypher` is a string (use `isinstance(generated_cypher, str)`). If it is not (or is None/falsy), return the "No Cypher query was generated." error and increment `cypher_retry_count` without calling `.strip()` or crashing.

3. **Silent Error Masking in Vector Search**:
   In `src/nodes.py` (`synthesize_response_node`), if `query_error` is present (not None), return a response that clearly reports the database failure (e.g., `"Database query execution failed. Error: [query_error]"`) and do not mask it with `"No records found matching criteria"`. This ensures database errors are surfaced instead of silently masked.

4. **Missing Fast-Fail on Blocked Modifying Cypher Queries**:
   In `src/main.py` (`check_execution_status`), if `error` is `"Modifying Cypher operations are blocked."`, bypass the retry loop and return `"synthesize_response"` immediately to fail fast.

5. **Mock Driver Parity (`MockRecord` Iteration)**:
   In `src/database.py` (`MockRecord.__iter__`), change the iterator to yield keys instead of values, aligning it with the real Neo4j `Record` class:
   ```python
   def __iter__(self):
       return iter(self._data.keys())
   ```

6. **System Prompt Injection Resiliency**:
   In `src/nodes.py` (`synthesize_response_node`), wrap the `user_query` inside `<user_query>...</user_query>` tags and update the prompt to instruct the LLM to ignore instructions nested inside those tags.

7. **Integrate Adversarial Test Cases**:
   Append the following tests to the end of `tests/test_e2e_opaque.py`:
   - `test_adversarial_cypher_drop_ddl_blocked`
   - `test_adversarial_vector_search_error_not_masked`
   - `test_adversarial_modify_fail_fast`
   - `test_adversarial_non_string_cypher_handling`
   - `test_adversarial_prompt_injection_guard`
   - `test_mock_record_iteration_parity`

## Instructions
1. Edit `src/nodes.py`, `src/main.py`, `src/database.py`, and `tests/test_e2e_opaque.py` to implement the above fixes and tests.
2. Run pytest: `.venv\Scripts\pytest tests/` and `python test_mock_driver.py` using `run_command` (if the prompt comes up, wait for user confirmation) to verify everything passes.
3. Write `handoff.md` detailing the changes and test results when complete.
