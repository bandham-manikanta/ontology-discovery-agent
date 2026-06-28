# Verification Guide: Enterprise Ontology Discovery Agent

Follow these exact steps to verify the initialization, connectivity checks, endpoint routing, and security policies of the Ontology Agent.

---

## 1. Prerequisites Setup

### A. Environment File
Verify that your `.env` file at the root contains the correct configurations:
```ini
NVIDIA_API_KEY=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
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
CHAT_MODEL=meta/llama-3.3-70b-instruct
EMBEDDING_MODEL=nvidia/nv-embedqa-e5-v5
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password123
```

### B. Start Neo4j Database
Start the Neo4j instance using Docker Compose:
```bash
docker compose up -d
```
*(Wait 10–15 seconds for the database port to bind and verify connectivity).*

---

## 2. Step 1: Database Seeding Verification

Run the database seeding script to configure constraints, create the vector index, and populate mock enterprise ontology data:
```bash
python src/seed_data.py
```

### Expected Output (Success):
```text
Setting up unique constraints and indexes...
Constraints and indexes configured successfully!
Generating embeddings and seeding enterprise ontology graph...
Generating embedding for dataset: Vehicle_Telemetry_Gold...
Generating embedding for dataset: Supplier_Invoices_Raw...
Generating embedding for dataset: Dealer_Financing_Silver...
Generating embedding for dataset: Legacy_FOTA_Logs...
Setting up node relationships...
Graph database seeding complete!
```

### Offline Verification (Error check):
Stop your docker container (`docker compose down`) and run the script again. It must abort and output:
```text
Error: Neo4j is offline. Details: Failed to establish connection...
```

---

## 3. Step 2: FastAPI Server Startup Checks

Start the FastAPI application:
```bash
uvicorn src.main:app --port 8000 --reload
```

### Expected Console Output (Success):
```text
Running startup connectivity checks...
Verifying Neo4j connection on app startup...
INFO:     Started server process [8000]
```

### Startup Blocks (Security Verification):
*   **Offline Neo4j:** If the database is offline when you launch the server, uvicorn will crash and raise a `RuntimeError` stating `Neo4j is offline.`
*   **Missing API Key:** Rename `NVIDIA_API_KEY` in `.env` to test. The server will refuse to boot and raise `ValueError: NVIDIA_API_KEY environment variable is missing or empty.`

---

## 4. Step 3: API Endpoint Functional Testing

Use `curl` or any API client (like Postman) to test the `/query` endpoint.

### Test Case A: Semantic Vector Search
Sends a conceptual query that must route to the vector search index (retrieves datasets via cosine similarity).

**Command:**
```bash
curl -X POST http://localhost:8000/query \
     -H "Content-Type: application/json" \
     -d '{"query": "Find gold tier datasets talking about vehicle telematics or GPS coordinate streams"}'
```

**Expected JSON Response:**
```json
{
  "response": "**Dataset Search Results: Vehicle Telematics...** [Grounded response containing Vehicle_Telemetry_Gold]",
  "meta": {
    "routing_decision": "vector_search",
    "compiled_cypher": null,
    "retry_count": 0,
    "has_errors": false
  }
}
```

---

### Test Case B: Relational Cypher Query
Sends a structural question about schema owners/linages. It must route to `graph_cypher`, compile Cypher, execute on Neo4j, and return results.

**Command:**
```bash
curl -X POST http://localhost:8000/query \
     -H "Content-Type: application/json" \
     -d '{"query": "Who owns the column speed_mph and what is its data type?"}'
```

**Expected JSON Response:**
```json
{
  "response": "The column speed_mph is owned by Alice Smith and has a data type of INT.",
  "meta": {
    "routing_decision": "graph_cypher",
    "compiled_cypher": "MATCH (d:Dataset)-[:HAS_COLUMN]->(c:Column {name: 'speed_mph'})-[:OWNED_BY]->(o:Owner) RETURN c.data_type AS data_type, o.name AS owner_name",
    "retry_count": 0,
    "has_errors": false
  }
}
```

---

### Test Case C: Direct Conversational Response
Sends a general greeting that requires no database lookup.

**Command:**
```bash
curl -X POST http://localhost:8000/query \
     -H "Content-Type: application/json" \
     -d '{"query": "Hello!"}'
```

**Expected JSON Response:**
```json
{
  "response": "Hello! I am the Enterprise Ontology Discovery Assistant...",
  "meta": {
    "routing_decision": "direct_respond",
    "compiled_cypher": null,
    "retry_count": 0,
    "has_errors": false
  }
}
```

---

### Test Case D: Cypher Write-Block Security Guard (Adversarial)
Sends a query requesting to write nodes. It must generate a write Cypher query, which is caught and blocked by the regex security check.

**Command:**
```bash
curl -X POST http://localhost:8000/query \
     -H "Content-Type: application/json" \
     -d '{"query": "Please CREATE a new Owner node named Eve in the database"}'
```

**Expected JSON Response (Execution Error Trapped):**
```json
{
  "response": "Database query execution timeout/limit exceeded. Self-correction loop broke.",
  "meta": {
    "routing_decision": "graph_cypher",
    "compiled_cypher": "CREATE (o:Owner {name: 'Eve'})",
    "retry_count": 4,
    "has_errors": true
  }
}
```
*(The server logs will output: `Blocking modifying Cypher query: CREATE (o:Owner {name: 'Eve'})`)*.

---

### Test Case E: Content-Type Validation Middleware
Verifies that the server returns a `415 Unsupported Media Type` if the header is incorrect.

**Command:**
```bash
curl -X POST http://localhost:8000/query \
     -H "Content-Type: text/plain" \
     -d '{"query": "Hello!"}'
```

**Expected HTTP Status:** `415 Unsupported Media Type`
**Response Body:**
```json
{
  "detail": "Unsupported Media Type"
}
```

---

## 5. Step 4: Run Programmatic Test Suite

To run all automated Pytest assertions:
```bash
pytest tests/
```
*(Confirms that E2E opaque pathways, retry loops, invalid types, and safety blocks pass with exit code 0).*
