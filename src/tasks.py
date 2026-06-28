import os
import json
from dotenv import load_dotenv

load_dotenv()

GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID")
GCP_LOCATION = os.getenv("GCP_LOCATION", "us-central1")
CLOUD_TASKS_QUEUE = os.getenv("CLOUD_TASKS_QUEUE")
SERVICE_URL = os.getenv("SERVICE_URL")  # The public URL of the deployed Cloud Run service

def enqueue_evaluation_task(user_query: str, raw_db_results: list, synthesized_response: str, run_id: str, service_url: str = None):
    """
    Enqueues an asynchronous evaluation task in GCP Cloud Tasks.
    If the GCP project or queue is not configured, it fails gracefully.
    """
    url_to_use = service_url if service_url else SERVICE_URL
    if not all([GCP_PROJECT_ID, CLOUD_TASKS_QUEUE, url_to_use]):
        print("GCP Cloud Tasks configuration missing. Skipping async evaluation enqueue.")
        return

    try:
        from google.cloud import tasks_v2
        client = tasks_v2.CloudTasksClient()
        
        # Construct the fully qualified queue name
        parent = client.queue_path(GCP_PROJECT_ID, GCP_LOCATION, CLOUD_TASKS_QUEUE)
        
        # Construct the task payload
        payload = {
            "user_query": user_query,
            "raw_db_results": raw_db_results,
            "synthesized_response": synthesized_response,
            "run_id": run_id
        }
        
        # Configure the HTTP target task
        task = {
            "http_request": {
                "http_method": tasks_v2.HttpMethod.POST,
                "url": f"{url_to_use.rstrip('/')}/evaluate",
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps(payload).encode("utf-8")
            }
        }

        # Inject OIDC token if service account is available
        service_account_email = os.getenv("OIDC_SERVICE_ACCOUNT_EMAIL")
        if service_account_email:
            task["http_request"]["oidc_token"] = {
                "service_account_email": service_account_email,
                "audience": url_to_use.rstrip('/')
            }
        
        # Create and dispatch the task
        response = client.create_task(request={"parent": parent, "task": task})
        print(f"Asynchronously enqueued Cloud Task: {response.name}")
    except ImportError:
        print("Warning: google-cloud-tasks library not installed. Skipping async evaluation enqueue.")
    except Exception as e:
        print(f"Error enqueuing Cloud Task: {e}")
