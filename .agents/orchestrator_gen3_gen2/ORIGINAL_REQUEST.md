# Original User Request

## Follow-up — 2026-06-27T04:59:13Z

An enterprise data catalog ontology assistant that routes user queries, generates Neo4j Cypher queries, self-corrects syntax errors, executes vector similarity searches, and synthesizes answers.

Working directory: C:\Users\bandh\Documents\projects_ws\ontology-discovery-agent
Integrity mode: development

## Requirements

### R1. State-Machine Orchestration
Implement a LangGraph StateGraph that routes user queries to:
* `vector_search`: For conceptual or semantic searches.
* `graph_cypher`: For relational queries (owners, lineages, dependencies).
* `direct_respond`: For general conversation.
If a Cypher query execution error occurs, trigger a self-correction compiler node. Limit the correction loop to a maximum of 4 retries.

### R2. FastAPI Service Endpoint & Middleware
Expose a `/query` endpoint using FastAPI to execute query payloads programmatically through the LangGraph flow. Include HTTP middleware that validates that all POST requests to `/query` supply an `application/json` content-type header, returning a `415 Unsupported Media Type` if missing.
* Payload: `{"query": "User query string"}`
* Output: `{"response": "Synthesized text response", "meta": {"routing_decision": "vector_search", "compiled_cypher": "MATCH ...", "retry_count": 0, "has_errors": false}}`

### R3. Strict Database Startup checks
Do not fall back to mock drivers. The database seeding script and FastAPI startup lifespan must verify connectivity to the local Neo4j instance (port 7687) and make a test embedding call to NVIDIA NIM. If either service is unreachable, abort startup and raise a meaningful `RuntimeError`/`ConnectionError`.

### R4. Model & Environment Configuration
Load `NVIDIA_API_KEY`, `NVIDIA_BASE_URL` (set to `https://integrate.api.nvidia.com/v1`), `CHAT_MODEL` (set to `meta/llama-3.3-70b-instruct`), and `EMBEDDING_MODEL` (set to `nvidia/nv-embedqa-e5-v5`) from a `.env` file.

### R5. Cypher Write Protection
Block any modifying Cypher operations (`CREATE`, `MERGE`, `SET`, `DELETE`, `REMOVE`, `DETACH`) case-insensitively using regex boundary checks before query execution.

## Acceptance Criteria

### Seeding Execution
- [ ] Running the database seeding script completes successfully after transient retries, establishing unique constraints and seeding 4 datasets, 3 domains, 7 columns, and 3 owners.

### Programmatic API Verification
- [ ] A POST request to `/query` with `"Find datasets talking about vehicle telematics"` succeeds, routing to vector search and returning telemetry datasets.
- [ ] A POST request to `/query` with `"Who owns the column speed_mph?"` succeeds, returning the owner as Alice Smith.
- [ ] A POST request to `/query` with `"Hello!"` succeeds, routing to direct response.
- [ ] A POST request to `/query` with text/plain Content-Type fails with status code 415.
- [ ] A POST request to `/query` attempting to write data (e.g., `CREATE`) is successfully blocked by the security checker.

## Follow-up — 2026-06-27T14:25:24Z

Your workspace is C:\Users\bandh\Documents\projects_ws\ontology-discovery-agent.
Your folder is C:\Users\bandh\Documents\projects_ws\ontology-discovery-agent\.agents\orchestrator_gen3_gen2.
Your identity is teamwork_preview_orchestrator.
Your objective is to decompose, plan, and orchestrate the implementation of the updated requirements listed in C:\Users\bandh\Documents\projects_ws\ontology-discovery-agent\.agents\orchestrator_gen3_gen2\ORIGINAL_REQUEST.md:
1. Update LangGraph StateGraph Cypher error self-correction loop to a maximum of 4 retries (previously 3).
2. Expose a `/query` endpoint using FastAPI to execute query payloads programmatically through the LangGraph flow. Include HTTP middleware that validates that all POST requests to `/query` supply an `application/json` content-type header, returning a `415 Unsupported Media Type` if missing or incorrect.
3. Block any modifying Cypher operations (`CREATE`, `MERGE`, `SET`, `DELETE`, `REMOVE`, `DETACH`) case-insensitively using regex boundary checks before query execution.
4. Verify database seeding script completes successfully after transient retries, establishing unique constraints and seeding 4 datasets, 3 domains, 7 columns, and 3 owners.
5. Verify programmatic API verification tests for:
   - Vehicle telematics query (routes to vector search and returns telemetry datasets)
   - speed_mph owner query (returns Alice Smith)
   - Hello! query (routes to direct response)
   - text/plain content type failure (status code 415)
   - blocked modifying Cypher query (security checks block CREATE / etc)
Do not fall back to mock drivers. The database seeding script and FastAPI startup lifespan must verify connectivity to the local Neo4j instance and make a test embedding call to NVIDIA NIM. Abort startup and raise RuntimeError/ConnectionError if unreachable.

You must spawn a teamwork_preview_worker to inspect the current code, implement the updates, and execute tests. Run a reviewer and challenger to ensure the implementation is robust. Write your progress to progress.md in your folder and report completion when all tasks are done.

