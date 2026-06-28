import os
import sys
import uuid
from typing import Dict, Any, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from langgraph.graph import StateGraph, END

# Ensure parent directory is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.graph_state import AgentState
from src.database import get_driver, close_driver, nvidia_client, EMBEDDING_MODEL, NVIDIA_API_KEY
from src.tasks import enqueue_evaluation_task
from src.nodes import (
    route_query_node,
    execute_hybrid_search_node,
    generate_cypher_node,
    guardrail_cypher_audit_node,
    execute_cypher_node,
    correct_cypher_node,
    synthesize_response_node,
    guardrail_response_audit_node
)

# =====================================================================
# 1. State Graph Construction (Multi-Agent Team)
# =====================================================================
workflow = StateGraph(AgentState)

# Register Nodes
workflow.add_node("route_query", route_query_node)
workflow.add_node("execute_hybrid_search", execute_hybrid_search_node)
workflow.add_node("generate_cypher", generate_cypher_node)
workflow.add_node("guardrail_cypher_audit", guardrail_cypher_audit_node)
workflow.add_node("execute_cypher", execute_cypher_node)
workflow.add_node("correct_cypher", correct_cypher_node)
workflow.add_node("synthesize_response", synthesize_response_node)

# Set Entrypoint
workflow.set_entry_point("route_query")

# A. Orchestrator Routing
def route_after_query(state: AgentState) -> str:
    decision = state.get("routing_decision")
    if decision == "vector_search":
        return "execute_hybrid_search"
    elif decision == "graph_cypher":
        return "generate_cypher"
    else:
        return "synthesize_response"

workflow.add_conditional_edges(
    "route_query",
    route_after_query,
    {
        "execute_hybrid_search": "execute_hybrid_search",
        "generate_cypher": "generate_cypher",
        "synthesize_response": "synthesize_response"
    }
)

# B. Hybrid Search routing
workflow.add_edge("execute_hybrid_search", "synthesize_response")

# C. Cypher Generation -> Safety Audit
workflow.add_edge("generate_cypher", "guardrail_cypher_audit")

# D. Safety Audit Routing
def check_audit_status(state: AgentState) -> str:
    error = state.get("query_execution_error")
    if error == "Modifying Cypher operations are blocked.":
        return "synthesize_response"
    return "execute_cypher"

workflow.add_conditional_edges(
    "guardrail_cypher_audit",
    check_audit_status,
    {
        "synthesize_response": "synthesize_response",
        "execute_cypher": "execute_cypher"
    }
)

# E. Cypher Execution Routing (Self-Correction Loop)
def check_execution_status(state: AgentState) -> str:
    error = state.get("query_execution_error")
    retry_count = state.get("cypher_retry_count", 0)
    
    if error is not None:
        if retry_count < 5:
            return "correct_cypher"
        else:
            return "synthesize_response"
    else:
        return "synthesize_response"

workflow.add_conditional_edges(
    "execute_cypher",
    check_execution_status,
    {
        "correct_cypher": "correct_cypher",
        "synthesize_response": "synthesize_response"
    }
)

# F. Self-Correction loops back to Safety Audit
workflow.add_edge("correct_cypher", "guardrail_cypher_audit")

# G. Response Synthesis -> End (Groundedness Audit is now asynchronous)
workflow.add_edge("synthesize_response", END)

# Compile Workflow Graph
workflow_graph = workflow.compile()


# =====================================================================
# 2. FastAPI Application Configuration
# =====================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup initialization
    print("Running startup connectivity checks...")
    
    # 1. Check NVIDIA_API_KEY
    if not NVIDIA_API_KEY:
        raise ValueError("NVIDIA_API_KEY environment variable is missing or empty.")
    
    # 2. Check NVIDIA NIM connectivity
    try:
        nvidia_client.embeddings.create(
            input=["test"],
            model=EMBEDDING_MODEL,
            extra_body={"input_type": "query"}
        )
    except Exception as e:
        raise RuntimeError(f"NVIDIA NIM is inactive/unreachable. Details: {e}")
        
    # 3. Check Neo4j connectivity
    try:
        get_driver().verify_connectivity()
    except Exception as e:
        raise RuntimeError(f"Neo4j is offline. Details: {e}")

    yield
    # Shutdown cleaning
    print("Closing database connections on shutdown...")
    close_driver()

app = FastAPI(
    title="Enterprise Ontology Discovery Engine",
    description="LangGraph-powered Neo4j and Nvidia NIM ontology agent.",
    lifespan=lifespan
)

from fastapi import Request
from fastapi.responses import JSONResponse

@app.middleware("http")
async def check_content_type_middleware(request: Request, call_next):
    if request.url.path == "/query" and request.method == "POST":
        content_type = request.headers.get("content-type", "")
        primary_media_type = content_type.split(";")[0].strip() if content_type else ""
        if primary_media_type != "application/json":
            return JSONResponse(status_code=415, content={"detail": "Unsupported Media Type"})
    return await call_next(request)

class QueryPayload(BaseModel):
    query: str

class EvalPayload(BaseModel):
    user_query: str
    raw_db_results: List[Dict[str, Any]]
    synthesized_response: str
    run_id: str

@app.post("/query")
async def process_ontology_query(payload: QueryPayload, background_tasks: BackgroundTasks, request: Request):
    query_text = payload.query
    if not query_text:
        raise HTTPException(status_code=400, detail="Missing text input query.")
    
    # Generate a unique run ID for tracing and evaluation matching
    run_uuid = uuid.uuid4()
    service_url = str(request.base_url)
    
    # Initialize LangGraph state
    initial_state = {
        "user_query": query_text,
        "routing_decision": "",
        "schema_metadata": (
            "Nodes: \n"
            "  Domain(name, description)\n"
            "  Dataset(name, tier, description, schema_summary)\n"
            "  Column(name, data_type, is_pii, description)\n"
            "  Owner(name, email, department)\n"
            "Relationships:\n"
            "  (dom:Domain)-[:CONTAINS]->(dat:Dataset)\n"
            "  (dat:Dataset)-[:HAS_COLUMN]->(col:Column)\n"
            "  (dat:Dataset)-[:OWNED_BY]->(own:Owner)\n"
            "  (dat:Dataset)-[:DEPENDS_ON]->(dat2:Dataset) (data lineage)"
        ),
        "generated_cypher": None,
        "query_execution_error": None,
        "raw_db_results": [],
        "cypher_retry_count": 0,
        "synthesized_response": ""
    }
    
    try:
        # Invoke the workflow with the run ID configured for LangSmith tracing
        final_output = workflow_graph.invoke(initial_state, config={"run_id": run_uuid})
        
        # Enqueue the evaluation task asynchronously in GCP Cloud Tasks
        background_tasks.add_task(
            enqueue_evaluation_task,
            user_query=query_text,
            raw_db_results=final_output.get("raw_db_results", []),
            synthesized_response=final_output.get("synthesized_response", ""),
            run_id=str(run_uuid),
            service_url=service_url
        )
        
        return {
            "response": final_output["synthesized_response"],
            "meta": {
                "routing_decision": final_output.get("routing_decision"),
                "compiled_cypher": final_output.get("generated_cypher"),
                "retry_count": final_output.get("cypher_retry_count", 0),
                "has_errors": final_output.get("query_execution_error") is not None
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Workflow execution failed: {e}")

@app.post("/evaluate")
async def evaluate_query_response(payload: EvalPayload):
    """
    Asynchronous endpoint invoked by GCP Cloud Tasks.
    Runs the LLM-as-a-Judge groundedness audit and logs the feedback to LangSmith.
    """
    print(f"Received evaluation task for Run ID: {payload.run_id}")
    
    # Reconstruct state for the auditor node
    state = {
        "raw_db_results": payload.raw_db_results,
        "synthesized_response": payload.synthesized_response,
        "query_execution_error": None
    }
    
    # Run the audit
    audit_result = guardrail_response_audit_node(state)
    
    # Log feedback to LangSmith if configured
    try:
        from langsmith import Client
        ls_client = Client()
        
        # Groundedness score: 0.0 if failed, 1.0 if passed
        has_failed = "Groundedness Audit Failed" in audit_result.get("synthesized_response", "")
        score = 0.0 if has_failed else 1.0
        comment = audit_result.get("synthesized_response", "Passed groundedness audit.")
        
        ls_client.create_feedback(
            run_id=payload.run_id,
            key="groundedness",
            score=score,
            comment=comment
        )
        print(f"Successfully logged groundedness feedback (score: {score}) to LangSmith for Run ID: {payload.run_id}")
    except Exception as e:
        print(f"Could not log feedback to LangSmith: {e}")
        
    return {"status": "success", "audit_completed": True}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
