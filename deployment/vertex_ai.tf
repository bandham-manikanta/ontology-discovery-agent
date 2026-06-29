# 1. GCP Cloud Tasks Queue for Rate-Limited Async Evaluation
resource "google_cloud_tasks_queue" "eval_queue" {
  name     = "ontology-eval-queue"
  location = var.region

  # Rate limit configuration to prevent hitting LLM API rate limits (avoiding HTTP 429s)
  rate_limits {
    max_dispatches_per_second = 2  # Strict rate-limiting of 2 dispatches per second
    max_concurrent_dispatches = 5  # Limits concurrent connections
  }

  retry_config {
    max_attempts       = 3
    min_backoff        = "5s"
    max_backoff        = "60s"
    max_doublings      = 3
  }

  depends_on = [google_project_service.apis]
}

# 2. Vertex AI Model Registry (Custom vLLM Serving Container) via gcloud upload
resource "null_resource" "upload_model" {
  provisioner "local-exec" {
    command = "gcloud ai models upload --region=${var.region} --project=${var.project_id} --model-id=vllm-qwen-2-5-7b --display-name=vllm-qwen-2-5-7b --container-image-uri=us-docker.pkg.dev/vertex-ai/prediction/vllm-gpu.0-4:latest --container-args=\"--model=Qwen/Qwen2.5-7B-Instruct,--max-model-len=4096,--tensor-parallel-size=1,--gpu-memory-utilization=0.85\" --container-ports=8080"
  }
  depends_on = [google_project_service.apis]
}

# 3. Vertex AI Endpoint
resource "google_vertex_ai_endpoint" "llama3_endpoint" {
  name         = "qwen-endpoint"
  location     = var.region
  display_name = "qwen-endpoint"
  description  = "Endpoint for serving Qwen 2.5 7B via vLLM"

  depends_on = [google_project_service.apis]
}


# Note: In a full deployment, you would deploy the model to the endpoint using:
# gcloud ai endpoints deploy-model llama-3-endpoint --model=vllm-llama-3-8b --display-name=llama-3-8b-awq --machine-type=g2-standard-4 --accelerator-type=NVIDIA_L4 --accelerator-count=1

resource "null_resource" "deploy_model" {
  provisioner "local-exec" {
    command = "gcloud ai endpoints deploy-model ${google_vertex_ai_endpoint.llama3_endpoint.name} --model=vllm-qwen-2-5-7b --display-name=qwen-2-5-7b --machine-type=g2-standard-4 --accelerator-type=NVIDIA_L4 --accelerator-count=1 --region=${var.region} --project=${var.project_id}"
  }
  depends_on = [
    google_vertex_ai_endpoint.llama3_endpoint,
    null_resource.upload_model
  ]
}

