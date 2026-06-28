# Project Plan: Enterprise Ontology Discovery Agent (GCP Demo Mode)

This plan outlines the milestones, architecture, and verification strategy to implement and deploy the Enterprise Ontology Discovery Agent on GCP in 'demo' integrity mode.

## Architecture & Requirements Mapping
- **R1. Agentic Graph-RAG (LangGraph & Neo4j)**: Expose a FastAPI app with a LangGraph StateGraph. Route queries to **Ontology Search Specialist** (hybrid search + RRF ranking) or **Cypher Specialist** (generate, execute, self-correct up to 4 retries, regex write blocker). Output formatted as an Interactive Markdown Catalog Sheet.
- **R2. Enterprise Model Serving (Vertex AI + vLLM)**: Terraform configurations to deploy Llama 3 8B (AWQ 4-bit quantized) using official GCP vLLM container on a Vertex AI Endpoint with a single NVIDIA L4 GPU.
- **R3. Rate-Limited Async Evaluation (GCP Cloud Tasks & LangSmith)**: Decouple LLM-as-a-Judge groundedness check via GCP Cloud Tasks queue. FastAPI returns response immediately and enqueues evaluation. `/evaluate` endpoint runs groundedness check and logs score to LangSmith.
- **R4. IaC & CI/CD (Terraform & GitHub Actions)**: Terraform configurations (`main.tf`, `vertex_ai.tf`) for Cloud Run, Cloud Tasks, Vertex AI, Secret Manager. GitHub Actions workflow (`.github/workflows/deploy.yml`) for automated container build and deploy.

---

## Milestones

| Milestone | Name | Scope / Objectives | Dependencies | Status |
|---|---|---|---|---|
| **M1** | Hybrid Search & RRF | Review and refine the Ontology Search Specialist hybrid search (Neo4j Vector + Full-Text) and RRF ranking in Python. Ensure response formatting matches the "Interactive Markdown Catalog Sheet" specification. | None | PLANNED |
| **M2** | Cypher Specialist & Safety | Review Cypher Specialist generation, execution, and self-correction (4 retries). Verify the regex Cypher write blocker is case-insensitive and robust. | None | PLANNED |
| **M3** | Model Serving (Vertex AI) | Verify and complete Terraform configurations for Vertex AI Endpoint deploying Llama 3 8B (AWQ 4-bit quantized) via vLLM on an L4 GPU. | None | PLANNED |
| **M4** | Async Evaluation | Verify and complete the Cloud Tasks integration, ensuring the `/query` endpoint enqueues evaluation tasks and the `/evaluate` endpoint executes groundedness audits and logs feedback to LangSmith. | M1, M2 | PLANNED |
| **M5** | IaC & CI/CD Setup | Verify and complete Terraform for Cloud Run, Cloud Tasks, and Secret Manager. Verify the GitHub Actions deployment workflow and Dockerfile. | M3, M4 | PLANNED |
| **M6** | End-to-End Verification | Run the full test suite (`pytest tests/`) to ensure all functional, security, and integration requirements pass. | M1-M5 | PLANNED |

---

## Verification Strategy
1. **Worker Verification**: The worker agent will make implementation adjustments, run local builds/tests, and verify that the application compiles and runs.
2. **Reviewer Verification**: The reviewer agent will review code changes, check against the requirements, and verify that the output formats and security policies are correct.
3. **Challenger Verification**: The challenger agent will verify correctness by running functional tests and stress-testing the endpoints (e.g. write-blocking, RRF ranking).
4. **Forensic Auditor Verification**: The auditor agent will perform integrity checks (ensuring no hardcoded results, authentic implementation) and provide a final clean verdict.
