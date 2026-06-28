# Codebase and Deployment Analysis Report

This report presents the findings, identified gaps, and recommendations from the read-only investigation of the Enterprise Ontology Discovery Agent codebase and deployment configuration.

---

## 1. R1: Agentic Graph-RAG

### Findings & Observations
- **Response Synthesizer Prompt (`src/nodes.py`, lines 126–163):**
  The prompt in `synthesize_response_node` instructs the LLM to write a "professional, grounded markdown response" and to "present structured lists or key findings in a clear, formatted layout". However, it **does not** explicitly mention or enforce the required output format: **"Interactive Markdown Catalog Sheet (including schema tables and lineage trees)"**.
- **Cypher Specialist Self-Correction Loop (`src/main.py`, lines 88–98):**
  The self-correction routing function `check_execution_status` checks:
  ```python
  if error is not None:
      if retry_count < 5:
          return "correct_cypher"
      else:
          return "synthesize_response"
  ```
  Since `cypher_retry_count` starts at `0` and increments by `1` on each database execution error (in `execute_cypher_node`), this loop allows up to **4 retries** (1 initial attempt + 4 retry attempts = 5 total attempts) before falling back to response synthesis. This is fully compliant with the 4-retry requirement.
- **Case-Insensitive Write-Blocking (`src/nodes.py`, lines 258–277):**
  The `guardrail_cypher_audit_node` implements case-insensitive write-blocking using a regular expression:
  ```python
  if re.search(r"\b(CREATE|MERGE|SET|DELETE|REMOVE|DETACH)\b", cleaned_cypher, re.IGNORECASE):
  ```
  This successfully blocks any query containing these write keywords as distinct word boundaries, regardless of case. If a write operation is detected, it increments `cypher_retry_count` and immediately routes to `synthesize_response` (bypassing the retry loop), which is the correct safety behavior.

### Gaps
1. The response synthesizer prompt does not instruct the LLM to format the response as an **"Interactive Markdown Catalog Sheet"** or to include **"schema tables"** and **"lineage trees"**.

### Recommendations
- **Update the response synthesizer prompt in `src/nodes.py`** to explicitly enforce the required format. The prompt should include instructions like:
  ```
  Rule 5: Format the output as an "Interactive Markdown Catalog Sheet".
  Rule 6: If the query results contain dataset columns or schema information, present them in a clear markdown "Schema Table" showing columns, data types, descriptions, and PII flags.
  Rule 7: If the query results contain lineage or dataset dependencies, represent them visually using a "Lineage Tree" (e.g., using text-based hierarchical rendering or mermaid.js syntax) based on (Dataset)-[:DEPENDS_ON]->(Dataset) relationships.
  ```

---

## 2. R2 & R4: Model Serving & IaC (Terraform)

### Findings & Observations
- **Vertex AI Model Deployment (`deployment/vertex_ai.tf`):**
  The configuration defines the model registry resource `google_vertex_ai_model.vllm_llama3` (lines 30–60) and the endpoint `google_vertex_ai_endpoint.llama3_endpoint` (lines 63–70). However, the actual resource to deploy the model to the endpoint (`google_vertex_ai_endpoint_deployed_model` or similar) is **completely missing**. Instead, there is only a commented-out note at the end of the file (lines 72–74) indicating that the model would be deployed via the `gcloud` CLI.
- **Required GCP Resources:**
  - **Cloud Run:** `google_cloud_run_v2_service.ontology_agent` is provisioned in `deployment/main.tf`.
  - **Cloud Tasks:** `google_cloud_tasks_queue.eval_queue` is provisioned in `deployment/vertex_ai.tf`.
  - **Vertex AI:** Model registry and endpoint are provisioned, but the model deployment is missing.
  - **Secret Manager:** Secrets are provisioned in `deployment/main.tf`, but the versions are not (which is expected for manual secret entry).

### Gaps
1. **Model Deployment Missing in IaC:** The model is not deployed to the endpoint via Terraform. If `terraform apply` is run, the endpoint will remain empty and unusable.
2. **Secret Manager IAM Permissions Missing:** There are no IAM resources (e.g., `google_secret_manager_secret_iam_member`) granting the Cloud Run service account permission to access the secrets (`NVIDIA_API_KEY`, `NEO4J_PASSWORD`, `NEO4J_URI`).
3. **Broad Service Account Permissions:** Cloud Run is configured to use the default Compute Engine service account by default, which violates the principle of least privilege.

### Recommendations
- **Add the `google_vertex_ai_endpoint_deployed_model` resource** to `deployment/vertex_ai.tf` to automate the deployment of the Llama 3 model to the endpoint:
  ```hcl
  resource "google_vertex_ai_endpoint_deployed_model" "llama3_deployed_model" {
    endpoint     = google_vertex_ai_endpoint.llama3_endpoint.id
    model        = google_vertex_ai_model.vllm_llama3.id
    display_name = "vllm-llama-3-8b-awq-deployed"
    
    dedicated_resources {
      machine_spec {
        machine_type      = "g2-standard-4"
        accelerator_type  = "NVIDIA_L4"
        accelerator_count = 1
      }
      min_replica_count = 1
      max_replica_count = 1
    }
  }
  ```
- **Add Secret Manager IAM bindings** in `deployment/main.tf` to grant the service account used by Cloud Run the `roles/secretmanager.secretAccessor` role on each secret:
  ```hcl
  resource "google_secret_manager_secret_iam_member" "secret_access" {
    for_each  = toset([
      google_secret_manager_secret.nvidia_api_key.id,
      google_secret_manager_secret.neo4j_password.id,
      google_secret_manager_secret.neo4j_uri.id
    ])
    secret_id = each.key
    role      = "roles/secretmanager.secretAccessor"
    member    = "serviceAccount:${google_service_account.cloud_run_sa.email}"
  }
  ```
- **Provision a dedicated service account** for Cloud Run in `deployment/main.tf` instead of using the default one.

---

## 3. R3: Async Evaluation

### Findings & Observations
- **Integration Flow (`src/main.py` & `src/tasks.py`):**
  The integration is architected as follows:
  1. `/query` processes the request and schedules a FastAPI background task `enqueue_evaluation_task`.
  2. `enqueue_evaluation_task` calls the GCP Cloud Tasks API to create a task in the queue.
  3. The task is dispatched by GCP Cloud Tasks to the `/evaluate` endpoint of the Cloud Run service.
  4. `/evaluate` runs the LLM-as-a-Judge groundedness audit and logs the results to LangSmith using `ls_client.create_feedback`.
- **GCP Cloud Tasks Configurations:**
  The `enqueue_evaluation_task` function retrieves configuration from environment variables: `GCP_PROJECT_ID`, `GCP_LOCATION`, `CLOUD_TASKS_QUEUE`, and `SERVICE_URL`.

### Gaps
1. **Missing Environment Variables in Deployment:** None of the required variables (`GCP_PROJECT_ID`, `GCP_LOCATION`, `CLOUD_TASKS_QUEUE`, `SERVICE_URL`) are defined in `deployment/main.tf` under the Cloud Run service environment variables, nor are they passed in the `.github/workflows/deploy.yml` deployment command. This causes the async evaluation task to be skipped silently.
2. **Circular Dependency on `SERVICE_URL`:** Hardcoding `SERVICE_URL` in Terraform is problematic because the Cloud Run URL is generated dynamically after deployment.
3. **Missing Dependency in `requirements.txt`:** `langsmith` is imported directly in `src/main.py` but is not explicitly listed in `requirements.txt` (it is pulled transitively via `langchain`, but should be listed explicitly).

### Recommendations
- **Configure Environment Variables in Terraform:** Update `deployment/main.tf` to pass `GCP_PROJECT_ID` and `CLOUD_TASKS_QUEUE`.
- **Dynamic Service URL Detection:** Instead of relying on a static `SERVICE_URL` environment variable, modify the `/query` endpoint in `src/main.py` to capture the base URL from the incoming request object and pass it dynamically:
  ```python
  @app.post("/query")
  async def process_ontology_query(payload: QueryPayload, request: Request, background_tasks: BackgroundTasks):
      # ...
      service_url = str(request.base_url)
      background_tasks.add_task(
          enqueue_evaluation_task,
          user_query=query_text,
          raw_db_results=final_output.get("raw_db_results", []),
          synthesized_response=final_output.get("synthesized_response", ""),
          run_id=str(run_uuid),
          service_url=service_url  # pass dynamically
      )
  ```
  Update `enqueue_evaluation_task` in `src/tasks.py` to accept and use this `service_url` parameter.
- **Add `langsmith`** explicitly to `requirements.txt`.

---

## 4. R4: CI/CD

### Findings & Observations
- **GitHub Workflow (`.github/workflows/deploy.yml`):**
  The workflow is syntactically valid and automates the build and push of the Docker image to GCP Artifact Registry, followed by a deployment to Cloud Run via `gcloud run deploy`.
- **Dockerfile:**
  The `Dockerfile` is well-structured, uses a multi-stage-like simple setup with `python:3.11-slim`, installs `build-essential` (needed for compiled dependencies), installs `requirements.txt`, copies `src/`, and runs `uvicorn src.main:app`.

### Gaps
1. **Missing Env Vars in CI/CD Deploy:** Similar to the Terraform configuration, the `gcloud run deploy` command in the GitHub Actions workflow does not set the `GCP_PROJECT_ID`, `GCP_LOCATION`, and `CLOUD_TASKS_QUEUE` environment variables.
2. **Hardcoded User:** The workflow hardcodes `--set-env-vars="NEO4J_USER=41538b94,..."`, which should ideally be parameterized or handled via Secret Manager.

### Recommendations
- **Update `.github/workflows/deploy.yml`** to include the missing environment variables in the `--set-env-vars` flag of the `gcloud run deploy` command.

---

## 5. Testing

### Findings & Observations
- **Broken Imports in Test Suite:**
  The test suite contains 85 tests across `tests/test_e2e_opaque.py` and `tests/test_neo4j_fallback.py`. However, running the test suite fails immediately during collection with an `ImportError`:
  ```
  ImportError: cannot import name 'execute_vector_search_node' from 'src.nodes'
  ```
  This occurs because the search node in `src/nodes.py` is named `execute_hybrid_search_node` (performing vector search + keyword search via Reciprocal Rank Fusion), but the test files still attempt to import and call `execute_vector_search_node`.

### Gaps
1. **Broken Tests:** The test suite is completely broken and cannot be run or collected by `pytest` due to the invalid import of `execute_vector_search_node`.

### Recommendations
- **Fix Test Imports and Calls:**
  1. In `tests/test_e2e_opaque.py`, remove `execute_vector_search_node` from the import statement on line 10 (it is not actually used in this file).
  2. In `tests/test_neo4j_fallback.py`:
     - Change the imports on lines 29 and 130 from `execute_vector_search_node` to `execute_hybrid_search_node`.
     - Update the calls on lines 42 and 139 from `execute_vector_search_node(initial_state)` to `execute_hybrid_search_node(initial_state)`.
