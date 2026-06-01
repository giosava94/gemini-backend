Run the FastAPI app locally:

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Start the server:

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

3. Health endpoint:

GET http://127.0.0.1:8000/api/v1/health
