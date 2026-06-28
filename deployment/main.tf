provider "google" {
  project = var.project_id
  region  = var.region
}

variable "project_id" {
  type        = string
  description = "The GCP Project ID"
}

variable "region" {
  type        = string
  default     = "us-central1"
  description = "The target GCP region"
}

variable "image_uri" {
  type        = string
  description = "The GCR/Artifact Registry container image URI for the FastAPI app"
}

# 1. Enable Required GCP APIs
resource "google_project_service" "apis" {
  for_each = toset([
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "vpcaccess.googleapis.com",
    "aiplatform.googleapis.com" # Vertex AI
  ])
  service            = each.key
  disable_on_destroy = false
}

# 2. Secret Manager Secrets for Environment Variables
resource "google_secret_manager_secret" "nvidia_api_key" {
  secret_id = "nvidia-api-key"
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret" "neo4j_password" {
  secret_id = "neo4j-password"
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret" "neo4j_uri" {
  secret_id = "neo4j-uri"
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

# 2.5. Dedicated Service Account and IAM Roles for Cloud Run
resource "google_service_account" "cloud_run_sa" {
  account_id   = "ontology-agent-sa"
  display_name = "Ontology Discovery Agent Service Account"
}

resource "google_secret_manager_secret_iam_member" "nvidia_api_key_accessor" {
  secret_id = google_secret_manager_secret.nvidia_api_key.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.cloud_run_sa.email}"
}

resource "google_secret_manager_secret_iam_member" "neo4j_password_accessor" {
  secret_id = google_secret_manager_secret.neo4j_password.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.cloud_run_sa.email}"
}

resource "google_secret_manager_secret_iam_member" "neo4j_uri_accessor" {
  secret_id = google_secret_manager_secret.neo4j_uri.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.cloud_run_sa.email}"
}

# 3. Cloud Run V2 Service
resource "google_cloud_run_v2_service" "ontology_agent" {
  name     = "ontology-discovery-agent"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.cloud_run_sa.email

    containers {
      image = var.image_uri

      ports {
        container_port = 8000
      }

      resources {
        limits = {
          cpu    = "2"
          memory = "4Gi"
        }
      }

      # Secrets mapped as environment variables
      env {
        name = "NVIDIA_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.nvidia_api_key.secret_id
            version = "latest"
          }
        }
      }

      env {
        name = "NEO4J_PASSWORD"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.neo4j_password.secret_id
            version = "latest"
          }
        }
      }

      env {
        name = "NEO4J_URI"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.neo4j_uri.secret_id
            version = "latest"
          }
        }
      }

      # Non-secret environment variables
      env {
        name  = "NEO4J_USER"
        value = "41538b94"
      }

      env {
        name  = "CHAT_MODEL"
        value = "meta/llama-3.3-70b-instruct"
      }

      env {
        name  = "EMBEDDING_MODEL"
        value = "nvidia/nv-embedqa-e5-v5"
      }

      env {
        name  = "NVIDIA_BASE_URL"
        value = "https://integrate.api.nvidia.com/v1"
      }

      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }

      env {
        name  = "GCP_LOCATION"
        value = var.region
      }

      env {
        name  = "CLOUD_TASKS_QUEUE"
        value = google_cloud_tasks_queue.eval_queue.name
      }
    }
  }

  depends_on = [
    google_project_service.apis,
    google_secret_manager_secret.nvidia_api_key,
    google_secret_manager_secret.neo4j_password,
    google_secret_manager_secret.neo4j_uri,
    google_service_account.cloud_run_sa,
    google_secret_manager_secret_iam_member.nvidia_api_key_accessor,
    google_secret_manager_secret_iam_member.neo4j_password_accessor,
    google_secret_manager_secret_iam_member.neo4j_uri_accessor
  ]
}

# 4. Allow Unauthenticated Public Ingress (For Demo Purposes)
resource "google_cloud_run_v2_service_iam_member" "public_access" {
  name     = google_cloud_run_v2_service.ontology_agent.name
  location = google_cloud_run_v2_service.ontology_agent.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}

output "service_url" {
  value       = google_cloud_run_v2_service.ontology_agent.uri
  description = "The public URL of the deployed FastAPI service"
}
