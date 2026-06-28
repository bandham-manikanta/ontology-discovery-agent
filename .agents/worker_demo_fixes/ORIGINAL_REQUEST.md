## 2026-06-28T00:51:24Z

You are the Worker subagent.
Your working directory is: C:\Users\bandh\Documents\projects_ws\ontology-discovery-agent\.agents\worker_demo_fixes
Your identity is: teamwork_preview_worker

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Your task is to implement all required fixes and updates to align the codebase, Terraform configurations, GitHub Actions workflow, and test suite with the requirements:

1. **Response Synthesizer Prompt (R1)**:
   - In `src/nodes.py`, update `synthesize_response_node` to modify the prompt for response synthesis. Explicitly instruct the LLM to format the final output as an "Interactive Markdown Catalog Sheet".
   - Instruct the LLM to include:
     - A clear markdown **"Schema Table"** showing columns, data types, descriptions, and PII flags if the results contain column or schema details.
     - A visual **"Lineage Tree"** (using text-based hierarchical rendering) representing dataset dependencies if the results contain lineage or dataset dependency information (based on `DEPENDS_ON` relationships).

2. **Async Evaluation & Service URL (R3)**:
   - In `src/main.py`:
     - Update `process_ontology_query` to accept the `Request` object (`request: Request`) and extract the base URL dynamically: `service_url = str(request.base_url)`.
     - Pass `service_url` as a keyword argument to `enqueue_evaluation_task` in the background tasks.
   - In `src/tasks.py`:
     - Update `enqueue_evaluation_task` to accept `service_url: str = None`.
     - If `service_url` is provided, use it for the task URL; otherwise, fall back to the `SERVICE_URL` environment variable.
   - In `requirements.txt`:
     - Add `langsmith` to the list of dependencies.

3. **Terraform Configurations (R2, R3, R4)**:
   - In `deployment/vertex_ai.tf`:
     - Add a `google_vertex_ai_endpoint_deployed_model` resource to deploy `google_vertex_ai_model.vllm_llama3` to `google_vertex_ai_endpoint.llama3_endpoint`. Use machine type `g2-standard-4` and accelerator `NVIDIA_L4` with count `1`.
   - In `deployment/main.tf`:
     - Create a dedicated service account for the Cloud Run service: `google_service_account.cloud_run_sa`.
     - Grant this service account the `roles/secretmanager.secretAccessor` role on each of the three secrets (`nvidia-api-key`, `neo4j-password`, `neo4j-uri`) using `google_secret_manager_secret_iam_member`.
     - Configure the Cloud Run service `google_cloud_run_v2_service.ontology_agent` to use this new service account.
     - Add the following environment variables to the Cloud Run service container:
       - `GCP_PROJECT_ID` (value of `var.project_id`)
       - `GCP_LOCATION` (value of `var.region`)
       - `CLOUD_TASKS_QUEUE` (value of `google_cloud_tasks_queue.eval_queue.name`)

4. **GitHub Actions Workflow (R4)**:
   - In `.github/workflows/deploy.yml`:
     - Update the `gcloud run deploy` command to include the missing environment variables in `--set-env-vars`:
       - `GCP_PROJECT_ID=${{ env.PROJECT_ID }}`
       - `GCP_LOCATION=${{ env.REGION }}`
       - `CLOUD_TASKS_QUEUE=ontology-eval-queue`

5. **Test Suite Imports**:
   - In `tests/test_e2e_opaque.py`, remove the unused import of `execute_vector_search_node`.
   - In `tests/test_neo4j_fallback.py`, change the imports and calls of `execute_vector_search_node` to `execute_hybrid_search_node`.

6. **Validation and Verification**:
   - Run the automated test suite locally (e.g. using `python run_all_tests.py` or `.venv\Scripts\pytest tests/`) and verify that all tests pass.
   - Run `terraform init` and `terraform validate` in the `deployment/` directory to verify that the Terraform configurations are valid.

Please document all your changes and verification results in a handoff report (`handoff.md`) in your working directory (`C:\Users\bandh\Documents\projects_ws\ontology-discovery-agent\.agents\worker_demo_fixes`), and send a message back to the parent (conversation ID: e40f08bb-ee07-4fc3-82ce-9ebc67477eef) when complete.
