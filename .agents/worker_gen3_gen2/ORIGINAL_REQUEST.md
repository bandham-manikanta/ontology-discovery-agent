## 2026-06-27T14:27:05Z
Verify and implement the updated requirements in C:\Users\bandh\Documents\projects_ws\ontology-discovery-agent:
1. Ensure the LangGraph StateGraph Cypher error self-correction loop is set to a maximum of 4 retries.
2. Validate the FastAPI `/query` endpoint exposes the programmatic query flow. Ensure it has HTTP middleware that validates that all POST requests to `/query` supply an `application/json` content-type header (case-insensitively, returning 415 if missing or incorrect).
3. Validate that any modifying Cypher operations (CREATE, MERGE, SET, DELETE, REMOVE, DETACH) are blocked case-insensitively using regex boundary checks before query execution.
4. Run the database seeding script `src/seed_data.py` (after verifying connectivity to local Neo4j and NVIDIA NIM without fallback to mock drivers), ensuring it establishes unique constraints and seeds exactly 4 datasets, 3 domains, 7 columns, and 3 owners.
5. Execute the programmatic API verification tests and confirm they all pass. The tests are:
   - Vehicle telematics query (routes to vector search, returns telemetry datasets)
   - speed_mph owner query (returns Alice Smith)
   - Hello! query (routes to direct response)
   - text/plain content type failure (status code 415)
   - blocked modifying Cypher query (security checks block CREATE, etc.)
Verify these by running pytest or python run_all_tests.py.
