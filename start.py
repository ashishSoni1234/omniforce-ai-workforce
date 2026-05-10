import subprocess
import time
import os
import sys
import requests

# Railway sets PORT for the public-facing port. Streamlit must bind there.
# FastAPI runs on a fixed internal port.
PORT = os.getenv("PORT", "8501")
FASTAPI_PORT = "8000"

print(f"[Start] Launching FastAPI on internal port {FASTAPI_PORT}...")
fastapi = subprocess.Popen([
    sys.executable, "-m", "uvicorn", "main:app",
    "--host", "0.0.0.0",
    "--port", FASTAPI_PORT
])

# /health now responds in ~2s (startup is non-blocking).
# Wait up to 60s max — if it doesn't start in 60s something is truly broken.
print("[Start] Waiting for FastAPI to be ready...")
for i in range(20):
    try:
        r = requests.get(f"http://localhost:{FASTAPI_PORT}/health", timeout=3)
        if r.status_code == 200:
            print(f"[Start] FastAPI ready after {i*3}s")
            break
    except Exception:
        pass
    time.sleep(3)
else:
    print("[Start] WARNING: FastAPI health check timed out — launching Streamlit anyway")

os.environ["BACKEND_URL"] = f"http://localhost:{FASTAPI_PORT}"
print(f"[Start] Launching Streamlit on public port {PORT}...")

streamlit = subprocess.Popen([
    sys.executable, "-m", "streamlit", "run", "demo/app.py",
    "--server.port", PORT,
    "--server.address", "0.0.0.0",
    "--server.headless", "true"
])

streamlit.wait()
fastapi.terminate()
