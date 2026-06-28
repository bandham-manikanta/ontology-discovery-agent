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

# 2. Variable for Hugging Face Token (required to download Llama 3 weights)
variable "hf_token" {
  type        = string
  sensitive   = true
  description = "Hugging Face API token to download Llama 3 8B weights"
}

# 3. Vertex AI Model Registry (Custom vLLM Serving Container)
resource "google_vertex_ai_model" "vllm_llama3" {
  name         = "vllm-llama-3-8b"
  location     = var.region
  display_name = "vllm-llama-3-8b-awq"
  description  = "Llama 3 8B served via vLLM with AWQ 4-bit quantization"

  container_spec {
    # Official Google Cloud Vertex AI pre-built vLLM container
    image_uri = "us-docker.pkg.dev/vertex-ai/prediction/vllm-gpu.0-4:latest"
    
    # vLLM serving arguments optimized for a single NVIDIA L4 GPU (24GB VRAM)
    args = [
      "--model=meta-llama/Meta-Llama-3-8B-Instruct",
      "--quantization=awq",
      "--max-model-len=4096",
      "--tensor-parallel-size=1",
      "--gpu-memory-utilization=0.85" # Leaves headroom for PagedAttention KV cache
    ]

    env {
      name  = "HF_TOKEN"
      value = var.hf_token
    }

    ports {
      container_port = 8080
    }
  }

  depends_on = [google_project_service.apis]
}

# 4. Vertex AI Endpoint
resource "google_vertex_ai_endpoint" "llama3_endpoint" {
  name         = "llama-3-endpoint"
  location     = var.region
  display_name = "llama-3-endpoint"
  description  = "Endpoint for serving Llama 3 8B AWQ via vLLM"

  depends_on = [google_project_service.apis]
}

# Note: In a full deployment, you would deploy the model to the endpoint using:
# gcloud ai endpoints deploy-model llama-3-endpoint --model=vllm-llama-3-8b --display-name=llama-3-8b-awq --machine-type=g2-standard-4 --accelerator-type=NVIDIA_L4 --accelerator-count=1

resource "google_vertex_ai_endpoint_deployed_model" "vllm_llama3_deployed" {
  endpoint           = google_vertex_ai_endpoint.llama3_endpoint.id
  model              = google_vertex_ai_model.vllm_llama3.id
  deployed_model_id  = "vllm_llama3_deployed"

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
