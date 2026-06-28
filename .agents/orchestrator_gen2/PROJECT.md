# Project: Ontology Discovery Agent

## Architecture
- **StateGraph**: Constructed using LangGraph. Routes user query to `vector_search`, `graph_cypher`, or `direct_respond`.
- **Database Layer**: Neo4j database driver connection with startup connectivity verification. Seeding script sets up constraints, vector index, and seeds static data.
- **FastAPI Layer**: Exposes `/query` POST endpoint, executing LangGraph and returning response with metadata.
- **NVIDIA NIM Integration**: Chat completions and embedding generation using NVidia APIs with startup validation in lifespan.

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | E2E Test Suite (Milestone 1) | Create comprehensive E2E tests (Tiers 1-4) | None | DONE |
| 2 | DB Seeding & Connectivity | Implement/verify database seeding and connectivity validation | None | DONE |
| 3 | StateGraph & Self-Correction | Implement/verify StateGraph routing and Cypher correction loop | M2 | DONE |
| 4 | Vector Similarity Search | Implement/verify vector similarity search using NVIDIA NIM | M2 | DONE |
| 5 | FastAPI `/query` Service | Expose API endpoint and integrate with LangGraph | M3, M4 | DONE |
| 6 | E2E Integration & Verification | Run full test suite, verify MockNeo4jDriver removal and startup check validation | M1, M5 | IN_PROGRESS (Gen 2 Orchestrator) |

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
- `src/database.py`: Neo4j driver connection, cosine similarity search, NVIDIA NIM client setup.
- `src/graph_state.py`: Definition of AgentState type.
- `src/seed_data.py`: Database constraint/index creation and mock/real data seeding with startup check.
