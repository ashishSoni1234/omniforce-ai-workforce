import io
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


@app.on_event("startup")
async def startup():
    import asyncio
    print("[OmniForce] AI Workforce starting up...")
    try:
        collection = initialize_chroma()
        if collection.count() == 0:
            print("[OmniForce] Collection empty - ingesting compliance documents...")
            count = ingest_sample_compliance_docs()
            print(f"[OmniForce] Compliance docs ingested: {count} documents")
        else:
            print(f"[OmniForce] ChromaDB ready: {collection.count()} chunks loaded")
    except Exception as e:
        print(f"[OmniForce] Startup warning (non-critical): {str(e)}")

    # Preload sanctions data so first KYC request is not slow
    try:
        from tools.sanctions_tool import _load_ofac_cache, _load_uk_cache
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _load_ofac_cache)
        await loop.run_in_executor(None, _load_uk_cache)
        print("[OmniForce] Sanctions data preloaded")
    except Exception as e:
        print(f"[OmniForce] Sanctions preload warning (non-critical): {str(e)}")


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
