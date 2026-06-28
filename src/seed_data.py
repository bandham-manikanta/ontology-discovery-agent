import os
import sys
# Make sure the parent directory is in python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import get_driver, get_embedding, close_driver, nvidia_client, EMBEDDING_MODEL, NVIDIA_API_KEY

def setup_constraints_and_indexes(session):
    print("Setting up unique constraints and indexes...")
    
    # 1. Uniqueness constraints
    for query in [
        "CREATE CONSTRAINT unique_domain_name IF NOT EXISTS FOR (d:Domain) REQUIRE d.name IS UNIQUE;",
        "CREATE CONSTRAINT unique_dataset_name IF NOT EXISTS FOR (d:Dataset) REQUIRE d.name IS UNIQUE;",
        "CREATE CONSTRAINT unique_column_name IF NOT EXISTS FOR (c:Column) REQUIRE c.name IS UNIQUE;",
        "CREATE CONSTRAINT unique_owner_name IF NOT EXISTS FOR (o:Owner) REQUIRE o.name IS UNIQUE;"
    ]:
        try:
            session.run(query)
        except Exception as e:
            if "already exists" not in str(e).lower():
                raise e
    
    # 2. Vector index for Dataset descriptions
    # Dimensions: 1024 (nvidia/nv-embedqa-e5-v5)
    try:
        session.run("""
        CREATE VECTOR INDEX dataset_description_embeddings IF NOT EXISTS
        FOR (d:Dataset) ON (d.embedding)
        OPTIONS {indexConfig: {
          `vector.dimensions`: 1024,
          `vector.similarity_function`: 'cosine'
        }};
        """)
    except Exception as e:
        if "already exists" not in str(e).lower():
            raise e
            
    # 3. Full-Text index for Dataset keyword search
    try:
        session.run("""
        CREATE FULLTEXT INDEX dataset_fulltext IF NOT EXISTS
        FOR (d:Dataset)
        ON EACH [d.name, d.description];
        """)
    except Exception as e:
        if "already exists" not in str(e).lower():
            raise e
    print("Constraints and indexes configured successfully!")

# Define datasets globally to allow pre-fetching of embeddings before starting Neo4j sessions
DATASETS = [
    {
        "name": "Vehicle_Telemetry_Gold", 
        "tier": "Gold", 
        "description": "Cleaned, real-time vehicle performance and location streams.",
        "schema_summary": "Contains automotive core signals: vin, latitude, speed_mph"
    },
    {
        "name": "Supplier_Invoices_Raw", 
        "tier": "Bronze", 
        "description": "Unfiltered ingestion of parts vendor billing records.",
        "schema_summary": "Contains supply operations signals: supplier_id, invoice_amount"
    },
    {
        "name": "Dealer_Financing_Silver", 
        "tier": "Silver", 
        "description": "Processed dealership credit and wholesale transactional data.",
        "schema_summary": "Contains dealer finance signals: tax_id, invoice_amount"
    },
    {
        "name": "Legacy_FOTA_Logs", 
        "tier": "Bronze", 
        "description": "Archived firmware-over-the-air installation histories.",
        "schema_summary": "Contains unmapped system text blobs"
    }
]

from typing import Optional

def seed_ontology_data(session, dataset_embeddings: Optional[dict] = None):
    print("Seeding enterprise ontology graph...")
    
    if not dataset_embeddings:
        dataset_embeddings = {}
        for ds in DATASETS:
            dataset_embeddings[ds["name"]] = get_embedding(ds["description"], input_type="passage")
            
    # 1. Domains
    domains = [
        {"name": "Connected_Vehicle", "description": "Telemetry, GPS, and sensor streaming data from field vehicles."},
        {"name": "Supply_Chain", "description": "Parts inventory, supplier logistics, and manufacturing procurement."},
        {"name": "Finance", "description": "Corporate accounting, dealership billing, and invoice processing."}
    ]
    for d in domains:
        session.run("""
        MERGE (dom:Domain {name: $name})
        ON CREATE SET dom.description = $description
        ON MATCH SET dom.description = $description
        """, d)
    
    # 2. Datasets (using pre-generated embeddings)
    for ds in DATASETS:
        embedding = dataset_embeddings[ds["name"]]
        session.run("""
        MERGE (d:Dataset {name: $name})
        ON CREATE SET d.tier = $tier, d.description = $description, d.schema_summary = $schema_summary, d.embedding = $embedding
        ON MATCH SET d.tier = $tier, d.description = $description, d.schema_summary = $schema_summary, d.embedding = $embedding
        """, {**ds, "embedding": embedding})
        
    # 3. Columns
    columns = [
        {"name": "vin", "data_type": "STRING", "is_pii": True, "description": "Vehicle Identification Number"},
        {"name": "latitude", "data_type": "FLOAT", "is_pii": True, "description": "Vehicle GPS coordinate latitude"},
        {"name": "speed_mph", "data_type": "INT", "is_pii": False, "description": "Current vehicle speed in miles per hour"},
        {"name": "supplier_id", "data_type": "STRING", "is_pii": False, "description": "Unique identifier for parts manufacturers"},
        {"name": "tax_id", "data_type": "STRING", "is_pii": True, "description": "Corporate or individual tax identifier"},
        {"name": "invoice_amount", "data_type": "DECIMAL", "is_pii": False, "description": "Gross monetary value of transaction"},
        # Edge case: Dirty column missing explicit PII classification
        {"name": "raw_payload", "data_type": "BLOB", "description": "Undocumented fallback data"}
    ]
    for c in columns:
        session.run("""
        MERGE (col:Column {name: $name})
        ON CREATE SET col.data_type = $data_type, col.is_pii = $is_pii, col.description = $description
        ON MATCH SET col.data_type = $data_type, col.is_pii = $is_pii, col.description = $description
        """, {
            "name": c["name"],
            "data_type": c.get("data_type"),
            "is_pii": c.get("is_pii"),
            "description": c.get("description")
        })
        
    # 4. Owners
    owners = [
        {"name": "Alice Smith", "email": "alice@enterprise.com", "department": "Telemetry Platform Engineering"},
        {"name": "Bob Jones", "email": "bob@enterprise.com", "department": "Global Procurement & Logistics"},
        {"name": "Charlie Brown", "email": "charlie@enterprise.com", "department": "Corporate Finance Operations"}
    ]
    for o in owners:
        session.run("""
        MERGE (own:Owner {name: $name})
        ON CREATE SET own.email = $email, own.department = $department
        ON MATCH SET own.email = $email, own.department = $department
        """, o)
        
    # 5. Establish Relationships
    print("Setting up node relationships...")
    
    # Domain -> Dataset
    session.run("MATCH (dom:Domain {name: 'Connected_Vehicle'}), (dat:Dataset {name: 'Vehicle_Telemetry_Gold'}) MERGE (dom)-[:CONTAINS]->(dat);")
    session.run("MATCH (dom:Domain {name: 'Supply_Chain'}), (dat:Dataset {name: 'Supplier_Invoices_Raw'}) MERGE (dom)-[:CONTAINS]->(dat);")
    session.run("MATCH (dom:Domain {name: 'Finance'}), (dat:Dataset {name: 'Dealer_Financing_Silver'}) MERGE (dom)-[:CONTAINS]->(dat);")
    
    # Dataset -> Column
    session.run("MATCH (dat:Dataset {name: 'Vehicle_Telemetry_Gold'}), (col:Column {name: 'vin'}) MERGE (dat)-[:HAS_COLUMN]->(col);")
    session.run("MATCH (dat:Dataset {name: 'Vehicle_Telemetry_Gold'}), (col:Column {name: 'latitude'}) MERGE (dat)-[:HAS_COLUMN]->(col);")
    session.run("MATCH (dat:Dataset {name: 'Vehicle_Telemetry_Gold'}), (col:Column {name: 'speed_mph'}) MERGE (dat)-[:HAS_COLUMN]->(col);")
    session.run("MATCH (dat:Dataset {name: 'Supplier_Invoices_Raw'}), (col:Column {name: 'supplier_id'}) MERGE (dat)-[:HAS_COLUMN]->(col);")
    session.run("MATCH (dat:Dataset {name: 'Supplier_Invoices_Raw'}), (col:Column {name: 'invoice_amount'}) MERGE (dat)-[:HAS_COLUMN]->(col);")
    session.run("MATCH (dat:Dataset {name: 'Dealer_Financing_Silver'}), (col:Column {name: 'tax_id'}) MERGE (dat)-[:HAS_COLUMN]->(col);")
    session.run("MATCH (dat:Dataset {name: 'Dealer_Financing_Silver'}), (col:Column {name: 'invoice_amount'}) MERGE (dat)-[:HAS_COLUMN]->(col);")
    session.run("MATCH (dat:Dataset {name: 'Legacy_FOTA_Logs'}), (col:Column {name: 'raw_payload'}) MERGE (dat)-[:HAS_COLUMN]->(col);")
    
    # Dataset -> Owner
    session.run("MATCH (dat:Dataset {name: 'Vehicle_Telemetry_Gold'}), (own:Owner {name: 'Alice Smith'}) MERGE (dat)-[:OWNED_BY]->(own);")
    session.run("MATCH (dat:Dataset {name: 'Supplier_Invoices_Raw'}), (own:Owner {name: 'Bob Jones'}) MERGE (dat)-[:OWNED_BY]->(own);")
    session.run("MATCH (dat:Dataset {name: 'Dealer_Financing_Silver'}), (own:Owner {name: 'Charlie Brown'}) MERGE (dat)-[:OWNED_BY]->(own);")
    
    # Dataset Data Lineage DEPENDS_ON
    session.run("MATCH (silver:Dataset {name: 'Dealer_Financing_Silver'}), (raw:Dataset {name: 'Supplier_Invoices_Raw'}) MERGE (silver)-[:DEPENDS_ON]->(raw);")
    
    print("Graph database seeding complete!")

def main():
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
        driver = get_driver()
        driver.verify_connectivity()
    except Exception as e:
        raise ConnectionError(f"Neo4j is offline. Details: {e}")
        
    try:
        # Pre-fetch all embeddings first on the host to avoid database inactivity timeouts
        dataset_embeddings = {}
        print("Generating embeddings via NVIDIA NIM...")
        for ds in DATASETS:
            print(f"Generating embedding for dataset: {ds['name']}...")
            dataset_embeddings[ds["name"]] = get_embedding(ds["description"], input_type="passage")
            
        # Separate the schema creation transaction to let it settle
        with driver.session() as session:
            setup_constraints_and_indexes(session)
            
        import time
        print("Waiting 3 seconds for schema indexes to settle...")
        time.sleep(3)
        
        # Seed ontology data with transient retry loop
        max_retries = 5
        for attempt in range(1, max_retries + 1):
            try:
                with driver.session() as session:
                    seed_ontology_data(session, dataset_embeddings)
                break
            except Exception as e:
                is_transient = "unavailable" in str(e).lower() or "transient" in str(e).lower() or "connection" in str(e).lower()
                if is_transient and attempt < max_retries:
                    print(f"Database transiently unavailable (attempt {attempt}/{max_retries}). Retrying in 3 seconds...")
                    time.sleep(3)
                else:
                    raise e
    except Exception as e:
        print(f"Failed to seed Neo4j: {e}", file=sys.stderr)
        raise e
    finally:
        close_driver()

if __name__ == "__main__":
    main()
