# Original User Request

## Initial Request — 2026-06-26T14:49:32-04:00

An enterprise data catalog ontology assistant that routes user queries, generates Neo4j Cypher queries, self-corrects syntax errors, executes vector similarity searches, and synthesizes answers.

Working directory: C:\Users\bandh\Documents\projects_ws\ontology-discovery-agent
Integrity mode: development

## Requirements

### R1. State-Machine Orchestration
Implement a LangGraph StateGraph that routes user queries to:
* `vector_search`: For conceptual or semantic searches.
* `graph_cypher`: For relational queries (owners, lineages, dependencies).
* `direct_respond`: For general conversation.
If a Cypher query execution error occurs, trigger a self-correction compiler node. Limit the correction loop to a maximum of 3 retries.

### R2. FastAPI Service Endpoint
Expose a `/query` endpoint using FastAPI to execute query payloads programmatically through the LangGraph flow:
* Payload: `{"query": "User query string"}`
* Output: `{"response": "Synthesized text response", "meta": {"routing_decision": "vector_search", "compiled_cypher": "MATCH ...", "retry_count": 0, "has_errors": false}}`

### R3. Neo4j & Mock Driver Integration
Implement standard Neo4j driver connection logic, but include a fallback to a `MockNeo4jDriver` if the connection fails (offline mode). The mock driver must simulate Cypher query execution against the static seed data and perform cosine similarity calculations for vector searches on the fly using NVIDIA NIM.

### R4. Model & Environment Configuration
Load `NVIDIA_API_KEY`, `NVIDIA_BASE_URL` (set to `https://integrate.api.nvidia.com/v1`), `CHAT_MODEL` (set to `meta/llama-3.3-70b-instruct`), and `EMBEDDING_MODEL` (set to `nvidia/nv-embedqa-e5-v5`) from a `.env` file.

## Acceptance Criteria

### Seeding Execution
- [ ] Running the database seeding script completes without error, establishing unique constraints and seeding 4 datasets, 3 domains, 7 columns, and 3 owners.

### Programmatic API Verification
- [ ] A POST request to `/query` with `"Find datasets talking about vehicle telematics"` succeeds, routing to vector search and returning telemetry datasets.
- [ ] A POST request to `/query` with `"Who owns the column speed_mph?"` succeeds, returning the owner as Alice Smith.
- [ ] A POST request to `/query` with `"Hello!"` succeeds, routing to direct response.

## Follow-up — 2026-06-27T02:44:49Z

Please run the tests and verify that the latest changes (removal of MockNeo4jDriver and addition of the NIM/Neo4j startup connectivity validation in the FastAPI lifespan and seed script) compile and run cleanly. Provide a progress report on the updated test outcomes.

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


## Follow-up — 2026-06-27T20:48:53-04:00

# Teamwork Project Prompt — Final

Implement and deploy the Enterprise Ontology Discovery Agent on Google Cloud Platform (GCP) according to the production-grade MLOps and Agentic architecture.

Working directory: `C:\Users\bandh\Documents\projects_ws\ontology-discovery-agent`
Integrity mode: demo

## Requirements

### R1. Agentic Graph-RAG (LangGraph & Neo4j)
The service must run a FastAPI application orchestrating a LangGraph `StateGraph` with a conditional routing node. Queries are routed to either:
1.  **Ontology Search Specialist:** Performs a hybrid search (Neo4j Vector Search + Neo4j Full-Text Index) and ranks results using Reciprocal Rank Fusion (RRF) in Python.
2.  **Cypher Specialist:** Generates, executes, and self-corrects Cypher queries against Neo4j (up to 4 retry loops), protected by a regex Cypher write blocker.
The final output must be formatted as an Interactive Markdown Catalog Sheet (including schema tables and lineage trees).

### R2. Enterprise Model Serving (Vertex AI + vLLM)
Write the Terraform configurations to deploy Llama 3 8B (AWQ 4-bit quantized) using the official GCP vLLM container on a Vertex AI Endpoint running on a single NVIDIA L4 GPU.

### R3. Rate-Limited Async Evaluation (GCP Cloud Tasks & LangSmith)
Decouple the LLM-as-a-Judge groundedness auditor from the live flow. The FastAPI app must return the response immediately and enqueue an evaluation task to a GCP Cloud Tasks queue. A `/evaluate` endpoint receives the task, runs the groundedness check, and logs a `groundedness` feedback score (1.0 or 0.0) to LangSmith.

### R4. IaC & CI/CD (Terraform & GitHub Actions)
Provide the complete Terraform configurations (`main.tf`, `vertex_ai.tf`) to provision all GCP resources (Cloud Run, Cloud Tasks, Vertex AI, Secret Manager) and a GitHub Actions workflow (`.github/workflows/deploy.yml`) to automate container building and deployment.

## Acceptance Criteria

### Core Functionality
- [ ] The `/query` endpoint successfully executes, returning a rich markdown response under 3 seconds.
- [ ] The `/query` endpoint successfully enqueues a task to the GCP Cloud Tasks queue.
- [ ] The `/evaluate` endpoint successfully executes the groundedness audit and logs the feedback to LangSmith.

### Infrastructure & Deployment
- [ ] Terraform files (`main.tf`, `vertex_ai.tf`) successfully initialize (`terraform init`) and validate (`terraform validate`).
- [ ] The GitHub Actions workflow (`deploy.yml`) is syntactically valid and configured to deploy to Cloud Run.
- [ ] The Dockerfile successfully builds the FastAPI application container.
