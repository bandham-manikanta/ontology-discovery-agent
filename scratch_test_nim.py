import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.database import nvidia_client

CHAT_MODEL = "meta/llama-3.3-70b-instruct"
schema_metadata = (
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
)
user_query = "Who owns the column speed_mph?"

prompt = (
    "You are a Neo4j Cypher expert.\n"
    f"Database Schema:\n{schema_metadata}\n\n"
    "Task: Write a Cypher query to retrieve information corresponding to the user's question.\n"
    "Rule 1: Only return the raw Cypher query string within code blocks. Do not append explanatory text.\n"
    "Rule 2: Do not write queries that modify the database (no CREATE, DELETE, SET, etc.). Use only read operations (MATCH, RETURN).\n"
    "Rule 3: Ensure relationship directions are correct. E.g. (Domain)-[:CONTAINS]->(Dataset), (Dataset)-[:HAS_COLUMN]->(Column), (Dataset)-[:OWNED_BY]->(Owner), (Dataset)-[:DEPENDS_ON]->(Dataset).\n"
    "Rule 4: Avoid returning entire nodes or relationships; instead, return properties with aliases like 'RETURN d.name AS dataset_name, o.name AS owner_name'.\n\n"
    f"User Question: {user_query}"
)

try:
    print("Sending Cypher generation completions request...")
    response = nvidia_client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        timeout=15.0
    )
    print("Response:")
    print(response.choices[0].message.content)
except Exception as e:
    print("Error:", e)
