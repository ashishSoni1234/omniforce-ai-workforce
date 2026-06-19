# OmniForce AI Workforce

**Autonomous AI agents for financial services automation**

Powered by Llama 3.3 70B (Groq), LangGraph, ChromaDB, and real integrations with Airtable, Gmail, Slack, OFAC sanctions data, FATF/Basel AML risk scoring, and Mindee OCR.

[![Status](https://img.shields.io/badge/status-production--ready-brightgreen)]()
[![Tests](https://img.shields.io/badge/tests-3%2F3%20passing-brightgreen)]()
[![Python](https://img.shields.io/badge/python-3.10--3.12-blue)]()
[![LLM](https://img.shields.io/badge/LLM-Llama%203.3%2070B-orange)]()

---

> **Live Demo:** [https://web-production-9a02d.up.railway.app](https://web-production-9a02d.up.railway.app)
> **Visual Demo Walkthrough:** [DEMO.md](./DEMO.md)
> **Full technical documentation:** [DOCUMENTATION.md](./DOCUMENTATION.md)
---

## What is OmniForce?

OmniForce deploys three autonomous AI agents that handle the most time-intensive workflows in financial services — without adding headcount.

| Agent | What it does |
|---|---|
| **Sales Agent** | Researches prospects, adds leads to Airtable CRM, sends follow-up emails via Gmail |
| **Ops Agent** | Processes invoices and timesheets, detects anomalies, routes approvals, generates reports |
| **KYC Agent** | Full AML/KYC pipeline — sanctions screening, country risk scoring, document verification, client onboarding |

---

## Architecture

```
User Request
     |
FastAPI /run endpoint
     |
LangGraph Orchestrator  (keyword-based routing)
     |
     +----------+----------+
     |          |          |
Sales Agent  Ops Agent  KYC Agent
     |          |          |
  Airtable   Slack    OFAC + UK Sanctions
  Gmail      Gmail    FATF + Basel AML Index
  DuckDuckGo  Groq    ChromaDB RAG
  Groq               Mindee OCR
                     Gmail + Slack
                     Groq Llama 3.3 70B
```

**KYC pipeline (7 steps):**
```
[1] Sanctions Check    OFAC XML (28MB) + UK HM Treasury CSV (47MB)
[2] AML Country Risk   FATF Black/Grey List + Basel AML Index 2023
[3] Document Check     Passport + Proof of Address + Bank Statement
[4] OCR Verification   Mindee API (optional, if image path provided)
[5] Compliance RAG     ChromaDB semantic search over policy PDFs
[6] Llama 3.3 70B      Augmented report using real data from steps 1-5
[7] Notifications      Gmail (missing docs / welcome) + Slack alert
```

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/<your-username>/omniforce-ai-workforce.git
cd omniforce-ai-workforce

# 2. Install
pip install -r requirements.txt

# 3. Configure
copy .env.example .env
# Fill in your API keys in .env

# 4. Download sanctions data
python scripts/download_data.py

# 5. Gmail setup (one time only)
python gmail_setup.py

# 6. Start backend
python -m uvicorn main:app --reload --port 8000

# 7. Start UI (new terminal)
streamlit run demo/app.py
```

---

## Environment Variables

```env
GROQ_API_KEY=               # console.groq.com
AIRTABLE_API_KEY=           # airtable.com/create/tokens
AIRTABLE_BASE_ID=
AIRTABLE_TABLE_NAME=Leads
SLACK_BOT_TOKEN=            # xoxb-...
SLACK_CHANNEL_ID=
GMAIL_CREDENTIALS_PATH=credentials.json
GMAIL_TOKEN_PATH=token.json
SENDER_EMAIL=

# Optional
OPENSANCTIONS_API_KEY=      # 500 free req/month
MINDEE_API_KEY=             # passport OCR
```

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/` | Status + agent list |
| GET | `/health` | Health check |
| POST | `/run` | Run any agent |
| POST | `/upload-invoice` | PDF invoice upload for Ops Agent |
| GET | `/leads` | Fetch all Airtable CRM leads |
| GET | `/docs` | FastAPI auto-generated docs |

---

## Example — KYC Check

```bash
curl -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -d '{
    "agent": "kyc",
    "instruction": "verify and check kyc documents for this client",
    "context": {
      "client_data": {
        "client_name": "Sarah Johnson",
        "email": "sarah@example.com",
        "country": "United Kingdom",
        "documents": ["Passport", "Proof of Address", "Bank Statement"]
      }
    }
  }'
```

**Response:**
```json
{
  "success": true,
  "result": {
    "status": "complete",
    "client_name": "Sarah Johnson",
    "missing_docs": [],
    "risk_level": "Medium",
    "email_sent": false,
    "sanctions_result": {
      "sanctioned": false,
      "risk_action": "PASS — No sanctions match found. Proceed with standard KYC."
    }
  }
}
```

---

## Example — Sales Lead Research

```bash
curl -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -d '{
    "agent": "sales",
    "instruction": "Find fintech companies in London doing £5-20M revenue",
    "context": {}
  }'
```

---

## Example — Invoice Processing

```bash
curl -X POST http://localhost:8000/upload-invoice \
  -F "file=@invoice.pdf" \
  -F "instruction=Process this invoice and check for anomalies"
```

---

## Test Results

```
python test_kyc_agent.py
```

| Test | Client | Scenario | Result |
|---|---|---|---|
| Test 1 | Sarah Johnson | All docs present | PASS |
| Test 2 | James Mitchell | Missing docs — email sent | PASS |
| Test 3 | Emma Williams | Full onboarding pipeline | PASS |

---

## Tech Stack

| Component | Technology |
|---|---|
| LLM | Llama 3.3 70B via Groq API |
| Orchestration | LangGraph StateGraph |
| Vector DB | ChromaDB (local persistent) |
| Embeddings | Hugging Face Inference API (langchain-huggingface) |
| Sanctions | OFAC SDN XML + UK HM Treasury CSV (local) |
| AML Risk | FATF Lists + Basel AML Index (embedded) |
| Document OCR | Mindee API |
| CRM | Airtable REST API |
| Email | Gmail API (OAuth 2.0) |
| Alerts | Slack Web API |
| Web Search | DuckDuckGo (no API key needed) |
| Backend | FastAPI + Uvicorn |
| Frontend | Streamlit |

---

## Project Structure

```
omniforce-ai-workforce/
+-- agents/          Sales, Ops, KYC agents + LangGraph orchestrator
+-- tools/           Airtable, Gmail, Slack, Sanctions, Risk, OCR, Search
+-- rag/             ChromaDB ingestion + semantic retrieval
+-- config/          Pydantic settings (single source for all env vars)
+-- models/          Pydantic request/response schemas
+-- data/sanctions/  OFAC (28MB) + UK (47MB) local sanctions lists
+-- demo/            Streamlit UI
+-- scripts/         Data download utilities
+-- main.py          FastAPI entry point
+-- gmail_setup.py   One-time Gmail OAuth token generator
+-- test_kyc_agent.py  Automated KYC test suite
```

**Full technical reference:** [DOCUMENTATION.md](./DOCUMENTATION.md)

---

## License

MIT
