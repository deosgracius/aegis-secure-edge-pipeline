# AEGIS control plane -- FastAPI + SQLite.
# Build from the repo root:  docker build -t aegis-control-plane .
FROM python:3.12-slim

WORKDIR /app

# Install deps first for layer caching
COPY control-plane/requirements.txt control-plane/requirements.txt
RUN pip install --no-cache-dir -r control-plane/requirements.txt

# App code: the control plane imports the knowledge graph from ../knowledge-graph
COPY control-plane/ control-plane/
COPY knowledge-graph/ knowledge-graph/

WORKDIR /app/control-plane
EXPOSE 8000

# 0.0.0.0 so the port is reachable from outside the container
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
