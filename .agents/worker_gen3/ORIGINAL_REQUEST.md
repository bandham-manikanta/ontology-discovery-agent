## 2026-06-27T05:04:23Z
You are a teamwork_preview_worker. Your working directory is C:\Users\bandh\Documents\projects_ws\ontology-discovery-agent\.agents\worker_gen3.
Your task is to implement the updated requirements and fix the existing bugs in the codebase.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Implementation Requirements:
1. State-Machine Orchestration retry limit:
   In `src/main.py` inside `check_execution_status`, update the comparison to `retry_count < 5` (permitting exactly 4 retries, previously 3, which was `retry_count < 4`).
   In `tests/test_e2e_opaque.py`, update `test_retry_tier1_max_retries_exceeded` and `test_retry_tier2_infinite_loop_prevention` to use `5` instead of `4` for the `cypher_retry_count` threshold.

2. FastAPI `/query` content-type middleware:
   In `src/main.py` inside `check_content_type_middleware`, extract the primary media type before verification by splitting on the parameter separator `;` (i.e. `content_type.split(";")[0].strip()`) and assert it matches exactly `"application/json"`. Return a `415 Unsupported Media Type` if it is missing or incorrect.

3. Cypher Security Blocking Check:
   In `src/nodes.py` line 88, update the write protection regex boundary check to block exactly (`CREATE`, `MERGE`, `SET`, `DELETE`, `REMOVE`, `DETACH`) case-insensitively using regex boundary checks before query execution.

4. Database seeding connectivity and checks:
   In `src/seed_data.py`, ensure that startup checks for NVIDIA_API_KEY, NVIDIA NIM connectivity, and Neo4j connectivity raise meaningful `ValueError`, `RuntimeError`, or `ConnectionError` respectively if unreachable (instead of calling `sys.exit(1)`).
   Ensure the database seeding script completes successfully after transient retries, establishing unique constraints and seeding 4 datasets, 3 domains, 7 columns, and 3 owners.

5. Test configuration for Real Integration runs:
   In `tests/conftest.py`, conditionally set the mock environment variables and skip mock client/driver setups if the environment variable `REAL_INTEGRATION=true` is set. This allows the integration tests to run against live services (Neo4j and NVIDIA NIM).

6. Discovered codebase bugs to resolve:
   - Positional arguments mismatch in `seed_ontology_data`: In `src/seed_data.py`, update `seed_ontology_data` signature to make `dataset_embeddings` optional (e.g. `dataset_embeddings: Optional[dict] = None`), and if it is None/empty, fetch them or handle it gracefully to avoid `TypeError` when tests invoke it with only `session`.
   - Test contamination in `test_config_tier1_custom_env_loader`: In `tests/test_e2e_opaque.py`, ensure that env vars `CHAT_MODEL` and `EMBEDDING_MODEL` are cleared/restored and the module reloaded at the end of the test.
   - Exception propagation in `route_query_node`: In `src/nodes.py`, wrap the openai completions API call in `route_query_node` in a try-except block to return `{"routing_decision": "graph_cypher"}` if LLM is offline/errors.
   - Invalid JSON body test failure: In `tests/test_e2e_opaque.py`, update `test_fastapi_tier2_invalid_json_body` to supply `headers={"Content-Type": "application/json"}` to bypass the content-type middleware.

7. Programmatic API integration tests to add:
   Add the following 5 API verification tests in `tests/test_e2e_opaque.py` (or a dedicated integration file), configuring them to support both mock mode (using `mock_openai` and `mock_neo4j` properties) and real integration mode (when `REAL_INTEGRATION=true`):
   - Vehicle telematics query (routes to vector search and returns telemetry datasets)
   - speed_mph owner query (returns Alice Smith)
   - Hello! query (routes to direct response)
   - text/plain content type failure (status code 415)
   - blocked modifying Cypher query (security checks block CREATE etc.)

Verification & Handoff:
- After applying the changes, run `python run_all_tests.py` (or run pytest directly) to verify that all tests pass.
- Write a handoff.md in your working directory with the list of changes made, build/test results, and verification command output. Send a message to the orchestrator when you are done.
