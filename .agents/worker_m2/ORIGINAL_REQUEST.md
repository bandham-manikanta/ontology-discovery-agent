## 2026-06-26T18:56:26Z
Objective: Implement the proposed fixes for Milestone 2 (DB Seeding & Fallback / Mock Driver Integration) in `src/database.py` and `src/seed_data.py`.

Here are the specific fixes to apply:
1. Fix Client Instantiation in `src/database.py` to prevent import crashes when `NVIDIA_API_KEY` is not set:
   ```python
   nvidia_client = OpenAI(
       api_key=NVIDIA_API_KEY or "dummy_key",
       base_url=NVIDIA_BASE_URL
   )
   ```
2. Make seeding idempotent in `src/seed_data.py` for Domains and Owners. Use:
   - For Domain:
     ```python
     MERGE (dom:Domain {name: $name})
     ON CREATE SET dom.description = $description
     ON MATCH SET dom.description = $description
     ```
   - For Owner:
     ```python
     MERGE (own:Owner {name: $name})
     ON CREATE SET own.email = $email, own.department = $department
     ON MATCH SET own.email = $email, own.department = $department
     ```
3. Prevent silent seeding failures in `src/seed_data.py`. If the driver is an instance of `MockNeo4jDriver`, print an error and exit with code 1.
4. Align `MockRecord` iteration with real Neo4j `Record` by returning values instead of keys:
   ```python
   def __iter__(self):
       return iter(self._data.values())
   ```
5. Cache static dataset description embeddings in `MockNeo4jDriver.__init__` to avoid redundant API calls on every vector search:
   ```python
   self.dataset_embeddings = {}
   for d in self.datasets:
       self.dataset_embeddings[d["name"]] = get_embedding(d["description"])
   ```
   And use this cached map in `mock_vector_search` instead of calling `get_embedding`.
6. Make JSON parsing in `mock_cypher_execute` robust by searching for markdown fences anywhere in the response:
   ```python
   match = re.search(r"```(?:json)?\s*(.*?)\s*```", resp_content, re.DOTALL | re.IGNORECASE)
   if match:
       resp_content = match.group(1).strip()
   ```

Verification instructions:
- Run an import test: Unset `NVIDIA_API_KEY` and run `python -c "import src.database"`. Ensure it does not crash.
- Run a record iteration test: Verify that `MockRecord` iteration yields the values of the record. E.g. running:
  ```python
  from src.database import MockRecord
  r = MockRecord({"name": "Alice"})
  print(list(r))  # should output ['Alice']
  ```
- Run a database seeding test: Ensure that seeding tries to run, or correctly exits with 1 when Neo4j is offline.

Working directory: C:\Users\bandh\Documents\projects_ws\ontology-discovery-agent\.agents\worker_m2
