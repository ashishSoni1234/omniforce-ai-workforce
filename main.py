import io
import threading
import os
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from models.schemas import TaskRequest
from agents.orchestrator import run_workflow
from rag.ingest import ingest_sample_compliance_docs, initialize_chroma

app = FastAPI(
    title="OmniForce AI Workforce",
    description="Autonomous AI agents for financial services automation",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_initialized = threading.Event()
_init_error: str = ""


def _background_init():
    global _init_error
    try:
        print("[OmniForce] Background init starting...")

        ofac_path = os.path.join("data", "sanctions", "ofac_sdn.xml")
        uk_path = os.path.join("data", "sanctions", "uk_sanctions.csv")
        if not os.path.exists(ofac_path) or not os.path.exists(uk_path):
            print("[OmniForce] Sanctions data missing — downloading now...")
            try:
                from scripts.download_data import download_sanctions_data
                download_sanctions_data()
                print("[OmniForce] Sanctions data downloaded")
            except Exception as e:
                print(f"[OmniForce] Sanctions download warning (non-critical): {e}")

        try:
            collection = initialize_chroma()
            if collection.count() == 0:
                print("[OmniForce] Collection empty - ingesting compliance documents...")
                count = ingest_sample_compliance_docs()
                print(f"[OmniForce] Compliance docs ingested: {count} documents")
            else:
                print(f"[OmniForce] ChromaDB ready: {collection.count()} chunks loaded")
        except Exception as e:
            print(f"[OmniForce] ChromaDB warning (non-critical): {e}")

        print("[OmniForce] Background init complete")
    except Exception as e:
        _init_error = str(e)
        print(f"[OmniForce] Background init error: {e}")
    finally:
        _initialized.set()


@app.on_event("startup")
async def startup():
    print("[OmniForce] AI Workforce starting up...")
    t = threading.Thread(target=_background_init, daemon=True)
    t.start()


@app.get("/")
def root():
    return {
        "status": "OmniForce AI Workforce Running",
        "version": "1.0.0",
        "agents": ["sales", "ops", "kyc"],
        "docs": "/docs",
    }


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.get("/ready")
def ready():
    if _initialized.is_set():
        if _init_error:
            return {"status": "degraded", "error": _init_error}
        return {"status": "ready"}
    return {"status": "initializing"}


@app.post("/run")
async def run_agent(request: TaskRequest):
    print(f"[API] /run called — agent: {request.agent}, instruction: {request.instruction[:60]}")
    try:
        context = request.context or {}
        result = run_workflow(
            task=request.instruction,
            instruction=request.instruction,
            document_content=context.get("document", ""),
            client_data=context.get("client_data", {}),
        )
        print(f"[API] /run complete — status: {result.get('status')}")
        return {"success": True, "result": result}
    except Exception as e:
        error_detail = f"Agent execution failed: {str(e)}"
        print(f"[API] /run error: {error_detail}")
        raise HTTPException(status_code=500, detail=error_detail)


@app.post("/upload-invoice")
async def upload_invoice(
    file: UploadFile = File(...),
    instruction: str = Form(default="Process this invoice and check for anomalies"),
):
    print(f"[API] /upload-invoice called — file: {file.filename}")
    try:
        import pdfplumber
        content = await file.read()
        if file.filename and file.filename.lower().endswith(".pdf"):
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                text = "\n".join(
                    page.extract_text() or "" for page in pdf.pages
                ).strip()
            if not text:
                raise HTTPException(status_code=422, detail="Could not extract text from PDF.")
        else:
            text = content.decode("utf-8", errors="ignore")

        from agents.ops_agent import OpsAgent
        agent = OpsAgent()
        result = agent.run(instruction, document_content=text)
        print(f"[API] /upload-invoice complete — status: {result.get('status')}")
        return {"success": True, "filename": file.filename, "result": result}
    except HTTPException:
        raise
    except Exception as e:
        error_detail = f"Invoice processing failed: {str(e)}"
        print(f"[API] /upload-invoice error: {error_detail}")
        raise HTTPException(status_code=500, detail=error_detail)


@app.get("/leads")
async def get_leads():
    print("[API] /leads called")
    try:
        from tools.airtable_tool import get_all_leads
        leads = get_all_leads()
        return {"leads": leads, "count": len(leads)}
    except Exception as e:
        error_detail = f"Failed to fetch leads: {str(e)}"
        print(f"[API] /leads error: {error_detail}")
        raise HTTPException(status_code=500, detail=error_detail)
