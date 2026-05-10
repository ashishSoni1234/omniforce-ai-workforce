#!/bin/bash
FASTAPI_PORT=8000

# Start FastAPI backend in background on internal port 8000
uvicorn main:app --host 0.0.0.0 --port $FASTAPI_PORT &

# Wait for FastAPI to be ready
sleep 8

# Start Streamlit on Railway's $PORT (public-facing)
BACKEND_URL=http://localhost:$FASTAPI_PORT streamlit run demo/app.py \
  --server.port ${PORT:-8501} \
  --server.address 0.0.0.0 \
  --server.headless true
