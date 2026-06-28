import os
import time
import json
import re
import math
from dotenv import load_dotenv
from neo4j import GraphDatabase
from openai import OpenAI

# Load environment variables
load_dotenv()

def clean_env_var(val: str) -> str:
    if not val:
        return val
    # Strip Byte Order Mark (BOM) and zero-width spaces
    return val.strip().replace("\ufeff", "").replace("\u200b", "")

# Read configurations
NEO4J_URI = clean_env_var(os.getenv("NEO4J_URI", "bolt://localhost:7687"))
NEO4J_USER = clean_env_var(os.getenv("NEO4J_USER", "neo4j"))
NEO4J_PASSWORD = clean_env_var(os.getenv("NEO4J_PASSWORD", "password123"))

NVIDIA_API_KEY = clean_env_var(os.getenv("NVIDIA_API_KEY"))
if not NVIDIA_API_KEY:
    NVIDIA_API_KEY = None
NVIDIA_BASE_URL = clean_env_var(os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1"))
CHAT_MODEL = clean_env_var(os.getenv("CHAT_MODEL", "meta/llama-3.3-70b-instruct"))
EMBEDDING_MODEL = clean_env_var(os.getenv("EMBEDDING_MODEL", "nvidia/nv-embedqa-e5-v5"))


# Optional Vertex AI Endpoint URL for private cloud serving
VERTEX_ENDPOINT_URL = os.getenv("VERTEX_ENDPOINT_URL")

def get_llm_client() -> OpenAI:
    if VERTEX_ENDPOINT_URL:
        try:
            import google.auth
            import google.auth.transport.requests
            
            # Retrieve Google Application Default Credentials (ADC)
            creds, project = google.auth.default()
            auth_req = google.auth.transport.requests.Request()
            creds.refresh(auth_req)
            
            print(f"Configuring LLM client to use Vertex AI Endpoint: {VERTEX_ENDPOINT_URL}")
            return OpenAI(
                base_url=VERTEX_ENDPOINT_URL,
                api_key=creds.token
            )
        except Exception as e:
            print(f"Warning: Failed to load Google Auth for Vertex AI. Falling back to NVIDIA NIM. Error: {e}")
            
    # Default fallback
    return OpenAI(
        api_key=NVIDIA_API_KEY or "dummy_key",
        base_url=NVIDIA_BASE_URL
    )

# Initialize LLM client
nvidia_client = get_llm_client()


def get_embedding(text: str, input_type: str = "query") -> list[float]:
    """Generates embedding using Nvidia NIM API."""
    if not NVIDIA_API_KEY:
        print("Warning: NVIDIA_API_KEY is not set. Generating a dummy embedding vector of 1024 dimensions.")
        return [0.0] * 1024
    
    try:
        response = nvidia_client.embeddings.create(
            input=[text],
            model=EMBEDDING_MODEL,
            extra_body={"input_type": input_type}
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"Error generating embedding: {e}. Falling back to dummy embedding.")
        return [0.0] * 1024

# --- Driver Factory Connection Initialization ---

def get_neo4j_driver(max_retries=3, delay=1):
    """Establishes Neo4j connection, raising ConnectionError if offline."""
    driver = None
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
            driver.verify_connectivity()
            return driver
        except Exception as e:
            last_error = e
            if driver:
                driver.close()
            if attempt < max_retries:
                time.sleep(delay)
    raise ConnectionError(
        f"Neo4j database is unreachable at {NEO4J_URI}. "
        "Please verify that the Neo4j Docker container is running and accessible on port 7687. "
        f"Details: {last_error}"
    )

# Global driver variable
_driver = None

def get_driver():
    global _driver
    if _driver is None:
        _driver = get_neo4j_driver()
    return _driver

def close_driver():
    global _driver
    if _driver is not None:
        _driver.close()
        _driver = None
