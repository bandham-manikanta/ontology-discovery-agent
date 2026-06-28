# Context: Enterprise Ontology Discovery Agent (GCP Demo Mode)

## Project Background
The Enterprise Ontology Discovery Agent is a LangGraph-based system that helps users navigate enterprise data catalogs. It routes queries to vector search or Cypher query generation based on query intent, executes those queries against a Neo4j database, and synthesizes responses.

For the production-grade GCP demo deployment, the agent's architecture includes:
1. **LangGraph & Neo4j**: Dynamic query routing, hybrid search (Neo4j Vector + Full-Text) with Reciprocal Rank Fusion (RRF), and a self-correcting Cypher specialist (4 retries) with case-insensitive write-blocking.
2. **Vertex AI & vLLM**: Terraform configurations to deploy Llama 3 8B (AWQ quantized) via vLLM on a single NVIDIA L4 GPU.
3. **GCP Cloud Tasks**: Asynchronous evaluation of groundedness via a `/evaluate` endpoint that logs feedback to LangSmith.
4. **Terraform & GitHub Actions**: Infrastructure as Code (IaC) and a CI/CD workflow to build and deploy to Cloud Run.

## Active Requirements
- **R1**: Hybrid search (vector + full-text) with RRF ranking. Response formatted as an Interactive Markdown Catalog Sheet (schema tables and lineage trees). Cypher specialist with 4 retries and write-blocking.
- **R2**: Terraform configuration for Llama 3 8B (AWQ) vLLM serving on Vertex AI (L4 GPU).
- **R3**: Rate-limited async evaluation via GCP Cloud Tasks queue. Groundedness audit on `/evaluate` logging score (1.0 or 0.0) to LangSmith.
- **R4**: Complete Terraform (`main.tf`, `vertex_ai.tf`) and GitHub Actions workflow (`deploy.yml`).

## System Integrity Mode
- **Integrity Mode**: `demo`
- **GCP Environment**: Simulated / dry-run. Terraform configurations must compile, initialize, and validate (`terraform init` and `terraform validate` must succeed).
- **Local Database**: A local Neo4j instance must be used for testing, and the python test suite must pass.
