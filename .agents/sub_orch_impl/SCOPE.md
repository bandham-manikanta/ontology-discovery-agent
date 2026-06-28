# Scope: Implementation Track

## Architecture
- **StateGraph**: LangGraph-based workflow running in `src/main.py` and `src/nodes.py`.
- **Database Layer**: Neo4j driver connection in `src/database.py` with mock driver fallback. Seeding script in `src/seed_data.py`.
- **FastAPI Layer**: Exposes `/query` POST endpoint in `src/main.py`.
- **NVIDIA NIM Integration**: Handles embed/chat API requests.

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 2 | DB Seeding & Fallback | Implement/verify database seeding and MockNeo4jDriver fallback | None | DONE |
| 3 | StateGraph & Self-Correction | Implement/verify StateGraph routing and Cypher correction loop | M2 | DONE |
| 4 | Vector Similarity Search | Implement/verify vector similarity search using NVIDIA NIM | M2 | DONE |
| 5 | FastAPI `/query` Service | Expose API endpoint and integrate with LangGraph | M3, M4 | DONE |
| 6 | E2E Integration & Tier 5 | Run E2E tests, fix issues, run Tier 5 adversarial testing | M2, M3, M4, M5 | DONE |

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
