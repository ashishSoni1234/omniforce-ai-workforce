import subprocess
import time
import os
import sys
import requests

PORT = os.getenv("PORT", "8501")
FASTAPI_PORT = "8080"

print(f"[Start] Launching FastAPI on port {FASTAPI_PORT}...")
fastapi = subprocess.Popen([
    sys.executable, "-m", "uvicorn", "main:app",
    "--host", "0.0.0.0",
    "--port", FASTAPI_PORT
])

print("[Start] Waiting for FastAPI to be ready...")
for i in range(120):
    try:
        r = requests.get(f"http://localhost:{FASTAPI_PORT}/health", timeout=2)
        if r.status_code == 200:
            print(f"[Start] FastAPI ready after {i*3}s")
            break
    except Exception:
        pass
    time.sleep(3)
else:
    print("[Start] FastAPI did not start in time — continuing anyway")

os.environ["BACKEND_URL"] = f"http://localhost:{FASTAPI_PORT}"
print(f"[Start] Launching Streamlit on port {PORT}...")

streamlit = subprocess.Popen([
    sys.executable, "-m", "streamlit", "run", "demo/app.py",
    "--server.port", PORT,
    "--server.address", "0.0.0.0",
    "--server.headless", "true"
])

streamlit.wait()
fastapi.terminate()
