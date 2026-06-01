FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UVICORN_WORKERS=1

# Create a non-root user and group for improved container security
RUN addgroup --system app && adduser --system --group app

# Set a working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt

# Copy application source with appropriate ownership
COPY --chown=app:app . /app

# Switch to non-root user
USER app

# Expose default FastAPI port
EXPOSE 8000

# Use production-ready ASGI server to run the app
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers ${UVICORN_WORKERS}"]
