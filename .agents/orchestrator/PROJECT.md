# Project: Ontology Discovery Agent

## Architecture
- **StateGraph**: Constructed using LangGraph. Routes user query to `vector_search`, `graph_cypher`, or `direct_respond`.
- **Database Layer**: Neo4j database driver connection with a fallback to `MockNeo4jDriver` if connection fails. Seeding script sets up constraints, vector index, and seeds static data.
- **FastAPI Layer**: Exposes `/query` POST endpoint, executing LangGraph and returning response with metadata.
- **NVIDIA NIM Integration**: Chat completions and embedding generation using NVidia APIs.

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | E2E Test Suite (Milestone 1) | Create comprehensive E2E tests (Tiers 1-4) | None | DONE (3c230876-1c8a-4b50-809d-297cc8be9e64) |
| 2 | DB Seeding & Fallback (Milestone 2) | Implement/verify database seeding and MockNeo4jDriver fallback | None | DONE (7919035e-9e97-4c0b-b4b4-319fa0ea8b9a) |
| 3 | StateGraph & Self-Correction (Milestone 3) | Implement/verify StateGraph routing and Cypher correction loop | M2 | DONE (7919035e-9e97-4c0b-b4b4-319fa0ea8b9a) |
| 4 | Vector Similarity Search (Milestone 4) | Implement/verify vector similarity search using NVIDIA NIM | M2 | DONE (7919035e-9e97-4c0b-b4b4-319fa0ea8b9a) |
| 5 | FastAPI `/query` Service (Milestone 5) | Expose API endpoint and integrate with LangGraph | M3, M4 | DONE (7919035e-9e97-4c0b-b4b4-319fa0ea8b9a) |
| 6 | E2E Integration & Tier 5 Hardening (Milestone 6) | Run full test suite, identify gaps, run adversarial testing | M1, M5 | DONE (7919035e-9e97-4c0b-b4b4-319fa0ea8b9a) |

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

## Code Layout
- `src/main.py`: LangGraph StateGraph, FastAPI server, lifespan events.
- `src/nodes.py`: Node functions for LangGraph (routing, generating, executing, correcting, vector search, synthesis).
- `src/database.py`: Neo4j driver connection, MockNeo4jDriver, cosine similarity search, NVIDIA NIM client setup.
- `src/graph_state.py`: Definition of AgentState type.
- `src/seed_data.py`: Database constraint/index creation and mock/real data seeding.
