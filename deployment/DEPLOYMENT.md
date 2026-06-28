# Enterprise Ontology Discovery Agent — Deployment & MLOps Guide

This guide outlines the production deployment architecture and step-by-step instructions for hosting the FastAPI agent on **Google Cloud Platform (GCP)** and connecting it to a high-performance private inference server running on the **Seawulf GPU Cluster**.

---

## 1. Production Architecture

```
                 +----------------------------------------------------+
                 |                    GCP Cloud                       |
                 |                                                    |
  User Request ->|  +----------------------------------------------+  |
                 |  |          GCP Cloud Run (FastAPI)             |  |
                 |  |  * Port: 8000                                |  |
                 |  |  * Orchestration: LangGraph                  |  |
                 |  +-----------------------+----------------------+  |
                 |                          |                         |
                 +--------------------------|-------------------------+
                                            |
                              Secure SSH Tunnel (Port 8081)
                                            |
                 +--------------------------v-------------------------+
                 |                 Seawulf HPC Cluster                |
                 |                                                    |
                 |  +----------------------------------------------+  |
                 |  |        SGLang LLM Inference Server           |  |
                 |  |  * Model: Llama-3.3-70B-Instruct-AWQ         |  |
                 |  |  * Hardware: NVIDIA A100 GPU                 |  |
                 |  +----------------------------------------------+  |
                 |                          |                         |
                 |                  Vector & Cypher                   |
                 |                          v                         |
                 |  +----------------------------------------------+  |
                 |  |             Neo4j AuraDB (Cloud)             |  |
                 |  +----------------------------------------------+  |
                 +----------------------------------------------------+
```

---

## 2. Infrastructure as Code (GCP Deployment)

The GCP infrastructure is managed via Terraform, located in [deployment/main.tf](file:///C:/Users/bandh/Documents/projects_ws/ontology-discovery-agent/deployment/main.tf). It provisions:
1.  **Google Cloud Run V2:** Hosts the Dockerized FastAPI application with auto-scaling.
2.  **Google Secret Manager:** Securely stores environment credentials (`NVIDIA_API_KEY`, `NEO4J_PASSWORD`, `NEO4J_URI`).
3.  **VPC / Public Ingress:** Enables secure public access to the `/query` endpoint.

### Steps to Deploy:
1.  **Build and Push the Container:**
    ```bash
    # Authenticate Docker to GCP Artifact Registry
    gcloud auth configure-docker us-central1-docker.pkg.dev

    # Build the image
    docker build -t us-central1-docker.pkg.dev/[PROJECT_ID]/ontology-agent/app:latest .

    # Push the image
    docker push us-central1-docker.pkg.dev/[PROJECT_ID]/ontology-agent/app:latest
    ```

2.  **Apply Terraform:**
    ```bash
    cd deployment
    terraform init
    terraform apply -var="project_id=[PROJECT_ID]" -var="image_uri=us-central1-docker.pkg.dev/[PROJECT_ID]/ontology-agent/app:latest"
    ```

---

## 3. Private GPU Inference (Seawulf SGLang Serving)

To serve the LLM locally on your provisioned Seawulf GPU, we use **SGLang** for high-performance structured output generation. 

### Why SGLang?
SGLang uses **RadixAttention**, which caches and reuses KV caches across multiple turns. Since our LangGraph agent executes multiple sequential LLM calls (Routing -> Cypher Gen -> Cypher Correction -> Response Synthesis), SGLang reduces latency by up to **5x** compared to standard serving.

### Step 1: Slurm Job Submission Script
Submit this job script on Seawulf to launch SGLang on a single NVIDIA A100 GPU:

```bash
#!/bin/bash
#SBATCH --job-name=sglang-llama3
#SBATCH --partition=gpu
#SBATCH --nodes=1
#SBATCH --gres=gpu:a100:1
#SBATCH --time=12:00:00
#SBATCH --output=sglang_%j.log

# Load CUDA modules
module load cuda/12.1

# Activate virtual environment
source ~/envs/sglang/bin/activate

# Launch SGLang with Llama 3.3 70B (AWQ Quantized to fit A100 40GB/80GB)
python -m sgl_intent.launch_server \
    --model-path casperhansen/llama-3-3-70b-instruct-awq \
    --port 8081 \
    --host 0.0.0.0 \
    --mem-fraction-static 0.8
```

### Step 2: Establish Secure Tunneling
Since Seawulf is behind a private network, establish a secure SSH reverse tunnel from the Seawulf login node to your GCP network or an intermediate gateway instance:

```bash
# Forward port 8081 on Seawulf GPU node to port 8081 on your GCP Gateway
ssh -N -R 8081:localhost:8081 user@gcp-gateway-ip
```

Update your Cloud Run environment variables to point `NVIDIA_BASE_URL` to `http://gcp-gateway-ip:8081/v1`.

---

## 4. AI Application Observability (LangSmith)

To satisfy the **AI application observability** requirement, the agent is pre-configured to stream traces directly to **LangSmith**. 

You do not need to modify any code. Simply sign up for a free account on [LangSmith](https://smith.langchain.com/) and append these variables to your [.env](file:///C:/Users/bandh/Documents/projects_ws/ontology-discovery-agent/.env) file:

```ini
# LangSmith Observability
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your-langsmith-api-key
LANGCHAIN_PROJECT=ontology-discovery-agent
```

Once added, restart your FastAPI server. Every agent routing decision, Cypher query execution, self-correction attempt, and response synthesis will be visualized in a real-time execution graph, allowing you to track:
1.  **Execution Paths:** Visualise exactly how the LangGraph traversed the nodes.
2.  **Latency Breakdown:** See which node (e.g., Cypher generation vs. Neo4j execution) took the most time.
3.  **Token Cost:** Monitor prompt and completion token counts per node.
