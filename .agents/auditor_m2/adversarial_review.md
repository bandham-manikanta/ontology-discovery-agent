## Challenge Summary

**Overall risk assessment**: MEDIUM

## Challenges

### [Medium] Challenge 1: `clean_cypher_query` Startswith Guard
- **Assumption challenged**: The LLM will always generate the Cypher query starting immediately with code fences (e.g. ````cypher`).
- **Attack scenario**: If the LLM generates a conversational preamble (e.g., *"Sure, here is your query:\n```cypher\nMATCH (n) RETURN n\n```"*), the function `clean_cypher_query` in `src/nodes.py` (Line 10) fails to strip the fences because the text does not start with triple backticks. It passes the raw markdown string directly to Neo4j, resulting in a syntax execution crash.
- **Blast radius**: The correction loop triggers and fails repeatedly if the LLM continues to generate preambles.
- **Mitigation**: Remove `startswith` check and search the entire string directly with regex (similar to `mock_cypher_execute`):
  ```python
  def clean_cypher_query(raw_query: str) -> str:
      cleaned = raw_query.strip()
      match = re.search(r"```(?:cypher)?\s*(.*?)\s*```", cleaned, re.DOTALL | re.IGNORECASE)
      if match:
          return match.group(1).strip()
      return cleaned
  ```

### [Low] Challenge 2: Whitespace in API Key Check
- **Assumption challenged**: `NVIDIA_API_KEY` is either a valid key or empty/unset (`None` or `""`).
- **Attack scenario**: If the key is set to a string containing only spaces (e.g. `"   "`), the truthiness checks `if not NVIDIA_API_KEY:` evaluate to `False`. The code proceeds to invoke the OpenAI client constructor and API, which will fail with HTTP unauthorized errors rather than triggering the offline fallback.
- **Blast radius**: Crashes or timeouts on vector search and cypher execution when starting the application in local environment with bad configuration.
- **Mitigation**: Use `not NVIDIA_API_KEY or not NVIDIA_API_KEY.strip()` for empty-value checks.

### [Low] Challenge 3: Caching Embeddings Input Type Mismatch
- **Assumption challenged**: Mock driver search is mathematically identical to real Neo4j vector search.
- **Attack scenario**: In `MockNeo4jDriver.__init__` (Line 122), it calls `get_embedding(d["description"])` which defaults to `input_type="query"`. In the real database seeding (`src/seed_data.py` Line 74), it uses `input_type="passage"`. Under NIM API, query and passage models may produce slightly different vectors, causing mock vector search rankings to differ mathematically from actual database search rankings.
- **Blast radius**: Minor discrepancy in search scores and test validations.
- **Mitigation**: Change mock initialization call to `get_embedding(d["description"], input_type="passage")`.

### [Low] Challenge 4: Non-JSON LLM Output in Mock Execution
- **Assumption challenged**: The LLM will always return a valid JSON list in `mock_cypher_execute`.
- **Attack scenario**: If the LLM generates a conversational response or a markdown block that is not standard JSON, `json.loads` raises a `JSONDecodeError`.
- **Blast radius**: The state graph will catch the exception and route to the correction node, but if the LLM output is structurally incorrect, the compiler node might struggle to debug it.
- **Mitigation**: Add a regex extraction helper for generic JSON lists (looking for matching `[` and `]`) as a fallback if direct parsing fails.

## Stress Test Results

- **LLM returns preamble + code block** → `clean_cypher_query` fails to strip markdown → query fails in Neo4j → **FAIL**
- **Whitespace-only API key configured** → client initialization goes through with whitespace API key → API calls crash → **FAIL**
- **Neo4j database offline during seeding** → `isinstance(driver, MockNeo4jDriver)` check fires → exits with status `1` → **PASS**

## Unchallenged Areas

- **FastAPI / Uvicorn Server Performance** — reason not challenged: beyond the scope of Milestone 2 core logic changes.
