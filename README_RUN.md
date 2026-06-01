Run the FastAPI app locally:

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Set Neo4j configuration as environment variables if needed:

```bash
export NEO4J_URI=bolt://localhost:7687
export NEO4J_USER=neo4j
export NEO4J_PASSWORD=password
```

3. Start the server:

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

4. Health endpoint:

GET http://127.0.0.1:8000/api/v1/health
