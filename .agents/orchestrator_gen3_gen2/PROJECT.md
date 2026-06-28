# Project: Ontology Discovery Agent (Gen 3 - Requirements Update)

## Architecture
- **StateGraph**: LangGraph-based query router (vector_search, graph_cypher, direct_respond). Cypher error self-correction node with a maximum of 4 retries.
- **FastAPI Layer**: Exposes `/query` POST endpoint, executing LangGraph and returning response with metadata. Includes HTTP middleware that validates that all POST requests to `/query` supply an `application/json` content-type header, returning a `415 Unsupported Media Type` if missing.
- **Database Layer**: Neo4j database driver connection. No fallback to mock drivers. Seeding script and FastAPI startup lifespan verify connectivity to the local Neo4j instance and make a test embedding call to NVIDIA NIM. Aborts startup and raises `RuntimeError`/`ConnectionError` if unreachable.
- **Cypher Write Protection**: Block any modifying Cypher operations (`CREATE`, `MERGE`, `SET`, `DELETE`, `REMOVE`, `DETACH`) case-insensitively using regex boundary checks before query execution.

## Milestones
| # | Name | Scope | Status |
|---|------|-------|--------|
| 1 | LangGraph Retry Limit | Update LangGraph StateGraph Cypher correction loop retry limit to a maximum of 4 retries | TODO |
| 2 | FastAPI 415 Middleware | Implement HTTP middleware validating `application/json` Content-Type header on `/query` POST, returning 415 if missing/invalid | TODO |
| 3 | Cypher Write Protection | Block modifying Cypher operations (`CREATE`, `MERGE`, `SET`, `DELETE`, `REMOVE`, `DETACH`) case-insensitively using regex boundary checks | TODO |
| 4 | Seeding Validation | Verify database seeding script completes successfully after transient retries (4 datasets, 3 domains, 7 columns, 3 owners) | TODO |
| 5 | E2E API Verification | Verify all acceptance criteria: telemetry query routing, column owner query routing, direct response routing, 415 response validation, and Cypher write protection blocking | TODO |

## Interface Contracts
### API Endpoint
- **URL**: `/query` (POST)
- **Request Payload**: `{"query": "..."}`
- **Response Schema**:
  ```json
  {
    "response": "...",
    "meta": {
      "routing_decision": "vector_search" | "graph_cypher" | "direct_respond",
      "compiled_cypher": "..." | null,
      "retry_count": int,
      "has_errors": boolean
    }
  }
  ```
