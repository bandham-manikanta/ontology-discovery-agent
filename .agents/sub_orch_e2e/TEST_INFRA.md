# E2E Test Infra: Ontology Discovery Agent

## Test Philosophy
- Opaque-box, requirement-driven. No dependency on implementation design.
- Methodology: Category-Partition + Boundary Value Analysis + Pairwise + Workload Testing.

## Feature Inventory
| # | Feature | Source (requirement) | Tier 1 | Tier 2 | Tier 3 |
|---|---------|---------------------|:------:|:------:|:------:|
| 1 | State-Machine Routing | ORIGINAL_REQUEST R1 | 5 | 5 | ✓ |
| 2 | FastAPI Service Endpoint | ORIGINAL_REQUEST R2 | 5 | 5 | ✓ |
| 3 | Neo4j & Mock Driver | ORIGINAL_REQUEST R3 | 5 | 5 | ✓ |
| 4 | Model & Env Configuration | ORIGINAL_REQUEST R4 | 5 | 5 | ✓ |
| 5 | Database Seeding Execution | ORIGINAL_REQUEST Seeding | 5 | 5 | ✓ |
| 6 | Cypher Self-Correction Loop | ORIGINAL_REQUEST R1 | 5 | 5 | ✓ |

## Test Architecture
- **Test runner**: `pytest` running with `pytest-mock` and `httpx` inside Python venv.
- **Invocation**: `pytest tests/`
- **Pass/fail semantics**: Exit code 0 indicates success. Non-zero indicates failure.
- **Test case format**: pytest test functions asserting HTTP status, payload schema, routing, retries, and fallback behaviors.
- **Directory layout**:
  - `tests/conftest.py`: Mocks for LLM client (`nvidia_client`), database connections, and standard fixtures.
  - `tests/test_e2e_opaque.py`: Tiers 1, 2, and 4 test cases.
  - `tests/test_neo4j_fallback.py`: Tier 3 driver connectivity fallback test cases.

## Real-World Application Scenarios (Tier 4)
| # | Scenario | Features Exercised | Complexity |
|---|----------|--------------------|------------|
| 1 | Semantic Search & Lineage lookup | F1, F2, F3, F4 | Medium |
| 2 | Complete User Session Flow | F1, F2 | Low |
| 3 | Database Seeding to Query Flow | F1, F2, F5 | Medium |
| 4 | DB Outage Recovery Flow | F2, F3 | High |
| 5 | Complex Ontology Analysis | F1, F2, F6 | High |

## Coverage Thresholds
- Tier 1: 30 test cases (5 per feature)
- Tier 2: 30 test cases (5 per feature)
- Tier 3: 6 test cases (cross-feature interactions)
- Tier 4: 5 test cases (realistic application scenarios)
- **Total Minimum**: 71 test cases
