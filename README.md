# Enterprise Ontology Discovery Agent

This project implements a state-of-the-art Enterprise Ontology Discovery Engine utilizing **FastAPI**, **LangGraph**, **Neo4j**, and **NVIDIA NIM** models.

## Architectural Setup

```text
enterprise-ontology-agent/
├── docker-compose.yml
├── requirements.txt
├── README.md
└── src/
    ├── __init__.py
    ├── main.py          # FastAPI application entrypoint and StateGraph orchestration
    ├── database.py      # Neo4j driver connection and vector index setup
    ├── graph_state.py   # LangGraph State schemas
    ├── nodes.py         # Stateful execution nodes (Route, Gen, Exec, Correct, VectorSearch, Synthesize)
    └── seed_data.py     # Idempotent script to populate Neo4j with mock enterprise ontology and embeddings
```

## Setup & Running Instructions

### 1. Build and Start Neo4j Container
Ensure Docker Desktop is running, then start the Neo4j instance:
```bash
docker-compose up -d
```

### 2. Create Virtual Environment and Install Dependencies
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Run the Database Seeding Script
This script populates the database and generates 1024-dimension embeddings via NVIDIA NeMo Retriever for the datasets:
```bash
python src/seed_data.py
```

### 4. Start the FastAPI API Server
```bash
uvicorn src.main:app --reload --port 8000
```

## API Endpoints

### Query Endpoint
* **URL:** `/query`
* **Method:** `POST`
* **Payload:**
  ```json
  {
    "query": "Find datasets related to driving patterns and GPS telematics"
  }
  ```
* **Response:**
  ```json
  {
    "response": "Based on the retrieved catalog results...",
    "meta": {
      "routing_decision": "vector_search",
      "compiled_cypher": null,
      "retry_count": 0,
      "has_errors": false
    }
  }
  ```
