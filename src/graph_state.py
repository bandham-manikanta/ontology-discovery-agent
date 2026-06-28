from typing import TypedDict, List, Dict, Any, Optional

class AgentState(TypedDict):
    user_query: str                  # Original input question
    routing_decision: str            # 'vector_search', 'graph_cypher', or 'direct_respond'
    schema_metadata: str             # Text schema representation injected for Cypher generation
    generated_cypher: Optional[str]  # The raw string output from the LLM text-to-cypher model
    query_execution_error: Optional[str] # Error log passed back from Neo4j driver during runtime
    raw_db_results: List[Dict[str, Any]] # Raw structural JSON arrays parsed from Neo4j (Cypher or Vector)
    cypher_retry_count: int          # Counter to control infinite correction loops
    synthesized_response: str        # Final human-readable response grounded in DB outputs
