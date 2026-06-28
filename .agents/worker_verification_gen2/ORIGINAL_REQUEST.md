## 2026-06-26T22:47:23Z
MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT
hardcode test results, create dummy/facade implementations, or
circumvent the intended task. A Forensic Auditor will independently
verify your work. Integrity violations WILL be detected and your
work WILL be rejected.

Task Description:
Your working directory is: C:\Users\bandh\Documents\projects_ws\ontology-discovery-agent\.agents\worker_verification_gen2
Please create this directory and initialize your progress.md there.

You need to fix the codebase and test suite issues that are causing the test suite to fail, verify that all 79 tests pass cleanly, and report the results.

Please make the following edits to the codebase and test files:

1. In C:\Users\bandh\Documents\projects_ws\ontology-discovery-agent\src\nodes.py:
   Remove all try-except blocks wrapping nvidia_client.chat.completions.create calls in the following nodes so that client exceptions propagate up to the workflow and caller instead of being caught and defaulted:
   - route_query_node (let exceptions bubble up, don't catch and default to "graph_cypher")
   - generate_cypher_node (let exceptions bubble up, don't catch and return query_execution_error)
   - correct_cypher_node (let exceptions bubble up, don't catch and return query_execution_error)
   - synthesize_response_node (let exceptions bubble up)
   Note: Do NOT remove the try-except block in execute_cypher_node or execute_vector_search_node, as those catch database execution errors to allow the self-correction loop or handle vector search query errors.

2. In C:\Users\bandh\Documents\projects_ws\ontology-discovery-agent\src\main.py:
   Add a middleware to check POST requests to `/query` and return 415 HTTP status code if the content-type is not "application/json".
   ```python
   from fastapi import Request
   from fastapi.responses import JSONResponse

   @app.middleware("http")
   async def check_content_type_middleware(request: Request, call_next):
       if request.url.path == "/query" and request.method == "POST":
           content_type = request.headers.get("content-type", "")
           if "application/json" not in content_type:
               return JSONResponse(status_code=415, content={"detail": "Unsupported Media Type"})
       return await call_next(request)
   ```

3. In C:\Users\bandh\Documents\projects_ws\ontology-discovery-agent\tests\conftest.py:
   - Import `httpx` at the top of the file.
   - Update `MockOpenAIClient.__init__` to initialize `self.base_url = httpx.URL("https://mock.nvidia.api/v1/")`.
   - Update `MockOpenAIClient.handle_chat` to use explicit `is not None` checks rather than the falsy `or` logic for custom mock attributes:
     - `res = self.custom_routing if self.custom_routing is not None else "graph_cypher"`
     - `res = self.custom_generation if self.custom_generation is not None else "```cypher\nMATCH (d:Domain) RETURN d.name AS domain_name\n```"`
     - `res = self.custom_correction if self.custom_correction is not None else "```cypher\nMATCH (d:Domain) RETURN d.name AS domain_name\n```"`
     - `res = self.custom_synthesis if self.custom_synthesis is not None else "This is a synthesized mock response."`

4. In C:\Users\bandh\Documents\projects_ws\ontology-discovery-agent\tests\test_e2e_opaque.py:
   - In `test_fallback_tier1_success_first_attempt`: Change the assertion `assert not isinstance(driver, MagicMock)` to `assert driver is not None`.
   - In `test_config_tier1_embedding_key_missing_fallback`: Use `monkeypatch.setattr(src.database, "NVIDIA_API_KEY", None)` instead of deleting it from environment and reloading the module.
   - In `test_fallback_tier2_port_offline_refused`: Wrap the driver call in `with pytest.raises(ConnectionError):` so the test expects the connection error.

After making these changes:
1. Run pytest (e.g. using `.venv2\Scripts\python.exe -m pytest tests/` or by running `python run_all_tests.py`).
2. Verify that all 79 tests collect and pass cleanly.
3. Write your handoff.md in C:\Users\bandh\Documents\projects_ws\ontology-discovery-agent\.agents\worker_verification_gen2\ explaining what changes were made and containing the full test output.
4. Send a message back to the parent (conversation ID: 5f1fa2ad-2805-45cc-9cbd-b3e37c7ecda8) when done.
