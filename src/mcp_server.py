import os
import re
from mcp.server.fastmcp import FastMCP
from src.database import get_driver, get_embedding

# Initialize FastMCP Server
mcp = FastMCP("Enterprise Ontology Discovery")

@mcp.tool()
def search_datasets_by_concept(concept: str) -> str:
    """
    Perform a vector similarity search in the enterprise ontology database
    to find datasets matching a conceptual description, topic, or domain.
    
    Args:
        concept: The search query (e.g., 'vehicle performance logs', 'invoice billing')
    """
    try:
        # 1. Generate query embedding
        query_vector = get_embedding(concept)
        
        # 2. Query Neo4j vector index
        driver = get_driver()
        cypher_query = """
        CALL db.index.vector.queryNodes('dataset_description_embeddings', 5, $embedding)
        YIELD node, score
        RETURN node.name AS dataset_name, node.tier AS tier, node.description AS description, node.schema_summary AS schema_summary, score
        """
        with driver.session() as session:
            result = session.run(cypher_query, {"embedding": query_vector})
            records = [dict(record) for record in result]
            
        if not records:
            return "No matching datasets found in the ontology catalog."
            
        # Format output as readable text
        output = ["### Matching Datasets (Vector Similarity):"]
        for r in records:
            output.append(
                f"- **{r['dataset_name']}** (Tier: {r['tier']}, Score: {r['score']:.4f})\n"
                f"  *Description:* {r['description']}\n"
                f"  *Schema:* {r['schema_summary']}"
            )
        return "\n".join(output)
    except Exception as e:
        return f"Error executing vector search: {str(e)}"

@mcp.tool()
def execute_read_only_cypher(query: str) -> str:
    """
    Execute a read-only Cypher query against the Neo4j enterprise ontology database
    to retrieve metadata about columns, owners, departments, and lineage.
    
    Args:
        query: A valid read-only Cypher query (e.g., 'MATCH (d:Dataset)-[:OWNED_BY]->(o:Owner) RETURN d.name, o.name')
    """
    # Clean the query
    cleaned_query = query.strip().strip("`")
    
    # Enforce read-only safety boundary
    if re.search(r"\b(CREATE|MERGE|SET|DELETE|REMOVE|DETACH)\b", cleaned_query, re.IGNORECASE):
        return "Security Block: Modifying Cypher operations (CREATE, MERGE, SET, DELETE, REMOVE, DETACH) are prohibited."
        
    try:
        driver = get_driver()
        with driver.session() as session:
            result = session.run(cleaned_query)
            records = [dict(record) for record in result]
            
        if not records:
            return "Query executed successfully. No records returned."
            
        # Format output as a markdown table
        headers = list(records[0].keys())
        table = [f"| {' | '.join(headers)} |", f"| {' | '.join(['---'] * len(headers))} |"]
        for r in records:
            row = [str(r.get(h, "")) for h in headers]
            table.append(f"| {' | '.join(row)} |")
            
        return "\n".join(table)
    except Exception as e:
        return f"Database execution error: {str(e)}"

if __name__ == "__main__":
    # Start the MCP server (communicates via stdio by default)
    mcp.run()
