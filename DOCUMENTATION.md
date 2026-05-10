# OmniForce AI Workforce — Full Technical Documentation

> Last updated: May 2026 | Status: Production-Ready | Tests: 3/3 Passing

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Architecture](#2-architecture)
3. [Project Structure](#3-project-structure)
4. [Tech Stack](#4-tech-stack)
5. [Agents](#5-agents)
   - [Sales Agent](#51-sales-agent)
   - [Ops Agent](#52-ops-agent)
   - [KYC Agent](#53-kyc-agent)
6. [Orchestrator (LangGraph)](#6-orchestrator-langgraph)
7. [Tools](#7-tools)
8. [RAG Pipeline](#8-rag-pipeline)
9. [API Reference](#9-api-reference)
10. [Environment Variables](#10-environment-variables)
11. [Setup Guide](#11-setup-guide)
12. [Gmail OAuth Setup](#12-gmail-oauth-setup)
13. [Test Results](#13-test-results)
14. [Data Sources](#14-data-sources)
15. [Known Limitations](#15-known-limitations)

---

## 1. System Overview

OmniForce AI Workforce is a **multi-agent AI automation platform** built for financial services firms. It deploys three autonomous AI agents that handle high-volume, compliance-sensitive workflows without human intervention.

### What it does

| Agent | Core Job | Integrations |
|---|---|---|
| Sales Agent | Lead research, CRM entry, email outreach | Airtable, Gmail, DuckDuckGo, Groq |
| Ops Agent | Invoice processing, anomaly detection, approval routing | Slack, Gmail, Groq |
| KYC Agent | Sanctions screening, AML risk scoring, document verification, client onboarding | OFAC, UK Sanctions, FATF, Basel AML Index, Gmail, Slack, ChromaDB |

### What makes it different

- **No LLM guessing for compliance** — KYC risk scoring uses real FATF lists + Basel AML Index data, not LLM hallucination
- **Real sanctions screening** — checks OFAC SDN (28MB) and UK HM Treasury lists locally, no per-call API cost
- **RAG-augmented compliance** — ChromaDB semantic search over real regulatory PDFs (FATF, MLR 2017, FCA SYSC 6)
- **Fully wired integrations** — Airtable, Gmail (OAuth 2.0), Slack Web API all live and tested

---

## 2. Architecture

```
                        USER REQUEST
                             |
                    FastAPI /run endpoint
                             |
                    LangGraph Orchestrator
                     (agents/orchestrator.py)
                             |
              +--------------+--------------+
              |              |              |
         router node    keyword match   route decision
              |
    +---------+---------+
    |         |         |
sales_node  ops_node  kyc_node
    |         |         |
    v         v         v
SalesAgent  OpsAgent  KYCAgent
    |         |         |
    +----+----+----+----+
         |    |    |    |
      Groq  Airtable  Gmail
      Llama  Slack   ChromaDB
      3.3    OFAC    FATF/Basel
      70B    UK San  RAG Docs


KYC Pipeline (7 steps):
========================
[1] Sanctions Check   -> OFAC XML + UK CSV (local, fuzzy match)
[2] AML Country Risk  -> FATF Black/Grey List + Basel AML Index
[3] Document Check    -> Required docs vs provided docs
[4] OCR Verification  -> Mindee API (if image path provided)
[5] Compliance RAG    -> ChromaDB semantic search over policy PDFs
[6] Llama Report      -> Groq LLM augmented with real data from 1-5
[7] Notifications     -> Gmail (missing docs / welcome) + Slack alert
```

---

## 3. Project Structure

```
omniforce-ai-workforce/
|
+-- agents/
|   +-- __init__.py
|   +-- orchestrator.py       LangGraph StateGraph — routes tasks to agents
|   +-- sales_agent.py        Lead research, CRM, email outreach
|   +-- ops_agent.py          Invoice processing, anomaly detection, routing
|   +-- kyc_agent.py          Full AML/KYC compliance pipeline
|
+-- config/
|   +-- __init__.py
|   +-- settings.py           Pydantic BaseSettings — single source for all env vars
|
+-- data/
|   +-- sanctions/
|       +-- ofac_sdn.xml      OFAC SDN List (28 MB — auto-downloaded)
|       +-- uk_sanctions.csv  UK FCDO Consolidated List (47 MB — auto-downloaded)
|
+-- demo/
|   +-- app.py                Streamlit UI — 3 agent tabs + leads table + PDF upload
|
+-- models/
|   +-- __init__.py
|   +-- schemas.py            Pydantic models: TaskRequest, KYCData, LeadRecord, etc.
|
+-- rag/
|   +-- __init__.py
|   +-- docs/                 Place compliance PDFs here (FATF, MLR, FCA)
|   +-- ingest.py             PDF/TXT ingestion pipeline (PyMuPDF + ChromaDB)
|   +-- retriever.py          Semantic search (sentence-transformers + ChromaDB)
|
+-- scripts/
|   +-- download_data.py      Auto-downloads OFAC + UK sanctions lists
|
+-- tools/
|   +-- __init__.py
|   +-- airtable_tool.py      Airtable REST API (add, get, update, search leads)
|   +-- document_verification.py  Mindee OCR — passport MRZ + field extraction
|   +-- gmail_tool.py         Gmail API OAuth 2.0 — send email, draft templates
|   +-- risk_scoring.py       FATF lists + Basel AML Index (deterministic, no LLM)
|   +-- sanctions_tool.py     OFAC XML + UK CSV screening with fuzzy name matching
|   +-- slack_tool.py         Slack Web API — alerts + structured ops reports
|   +-- web_search_tool.py    DuckDuckGo search — company research + lead data
|
+-- chroma_db/                ChromaDB persistent vector store (auto-created)
+-- .env                      Your API keys (never commit)
+-- .env.example              Template with all required variables
+-- main.py                   FastAPI entry point + startup events
+-- requirements.txt          All Python dependencies
+-- gmail_setup.py            One-time Gmail OAuth token generator
+-- test_kyc_agent.py         Automated test suite for KYC agent (3 tests)
+-- README.md                 Quick-start guide
+-- DOCUMENTATION.md          This file — full technical reference
```

---

## 4. Tech Stack

| Layer | Technology | Version |
|---|---|---|
| LLM | Llama 3.3 70B via Groq API | groq 0.9+ |
| Agent Orchestration | LangGraph StateGraph | langgraph 0.2.28 |
| Vector DB | ChromaDB (local persistent) | chromadb 0.5.18 |
| Embeddings | sentence-transformers/all-MiniLM-L6-v2 | 3.3.1 |
| AML Risk Data | FATF Lists + Basel AML Index (embedded) | Built-in |
| Sanctions | OFAC SDN XML + UK HM Treasury CSV | Local files |
| Document OCR | Mindee API | mindee (optional) |
| CRM | Airtable REST API | pyairtable 2.3.3 |
| Email | Gmail API (OAuth 2.0) | google-api-python-client |
| Alerts | Slack Web API | slack-sdk 3.33.3 |
| Web Search | DuckDuckGo (duckduckgo-search) | No API key needed |
| Backend | FastAPI + Uvicorn | fastapi 0.115.5 |
| Frontend | Streamlit | 1.40.1 |
| PDF Processing | PyMuPDF (fitz) + pdfplumber | Both installed |
| Config | Pydantic Settings + python-dotenv | pydantic-settings 2.6.1 |

---

## 5. Agents

### 5.1 Sales Agent

**File:** `agents/sales_agent.py`

**Purpose:** Automates the top-of-funnel sales workflow — finding prospects, adding them to CRM, and sending outreach emails.

**Instruction routing:**

| Keywords in instruction | Action |
|---|---|
| `find`, `research`, `prospect` | Web search → parse leads → add to Airtable → Slack alert |
| `follow`, `email`, `chase` | Extract company → search CRM → draft + send follow-up email |
| `update`, `crm`, `status` | Extract company + status → update Airtable record |
| anything else | Pass to Llama with sales context |

**Example calls:**
```json
{ "agent": "sales", "instruction": "Find 5 fintech companies in London doing £5-20M revenue" }
{ "agent": "sales", "instruction": "Send follow-up email to Acme Corp" }
{ "agent": "sales", "instruction": "Update status of TechVentures to Qualified" }
```

**Returns:**
```json
{
  "status": "complete",
  "leads_added": 5,
  "summary": "Found and added 5 fintech leads in London..."
}
```

---

### 5.2 Ops Agent

**File:** `agents/ops_agent.py`

**Purpose:** Processes operational documents — invoices, timesheets, contracts — and routes approvals.

**Instruction routing:**

| Keywords | Action |
|---|---|
| `invoice`, `timesheet`, `process` | Extract fields from document, detect anomalies, Slack alert |
| `approve`, `route`, `review` | Determine approval tier (Low/Medium/High), Slack routing |
| `report`, `summary` | Generate professional ops report, send to Slack |

**Approval tiers:**
- Low: < £1,000 — auto-approve
- Medium: £1,000–£10,000 — manager review
- High: > £10,000 — director sign-off

**Example calls:**
```json
{
  "agent": "ops",
  "instruction": "Process this invoice and check for anomalies",
  "context": { "document": "Invoice #1234\nVendor: ABC Ltd\nAmount: £15,000..." }
}
```

---

### 5.3 KYC Agent

**File:** `agents/kyc_agent.py`

**Purpose:** Full AML/KYC compliance pipeline for client onboarding.

**Instruction routing:**

| Keywords | Handler | Pipeline steps |
|---|---|---|
| `check`, `verify`, `kyc` | `_handle_document_check()` | Sanctions → AML risk → Doc check → OCR → RAG → Llama → Notify |
| `risk`, `assess` | `_handle_risk_assessment()` | Sanctions → Country risk → Llama risk score → Slack |
| `onboard`, `new client` | `_handle_onboarding()` | Full doc check + risk + onboarding report + welcome email + Slack |

**Required documents (REQUIRED_DOCUMENTS):**
- Passport
- Proof of Address
- Bank Statement

**Risk scoring logic:**

```
Base score (from real data):
  FATF Black List country  → +40 points
  FATF Grey List country   → +25 points
  Basel AML score >= 7.0   → +20 points
  Basel AML score >= 5.5   → +10 points
  Sanctions match          → +50 points

Client-specific score (from Llama): 0–30 points

Final score:
  0–30   → Low risk    (Simplified Due Diligence)
  31–60  → Medium risk (Customer Due Diligence)
  61–100 → High risk   (Enhanced Due Diligence)
```

**email_sent field:**
`email_sent: true` means conditions were met to send email (missing docs + email address present). Actual delivery depends on Gmail token being configured.

**Example calls:**
```json
{
  "agent": "kyc",
  "instruction": "verify and check kyc documents for this client",
  "context": {
    "client_data": {
      "client_name": "James Mitchell",
      "email": "james@example.com",
      "documents": ["Passport"]
    }
  }
}
```

---

## 6. Orchestrator (LangGraph)

**File:** `agents/orchestrator.py`

**Graph structure:**

```
START --> router --> [conditional edge] --> sales_node --> END
                                       --> ops_node   --> END
                                       --> kyc_node   --> END
```

**WorkflowState TypedDict fields:**
```python
task: str
agent_type: str          # set by router: "sales" | "ops" | "kyc"
instruction: str
document_content: str    # for Ops Agent (invoice text)
client_data: dict        # for KYC Agent
result: Optional[dict]
error: Optional[str]
status: str              # "pending" | "complete" | "error"
```

**Router keyword scoring:**

| Keywords | Agent |
|---|---|
| `lead`, `prospect`, `crm`, `sales`, `follow`, `email`, `company`, `revenue` | sales |
| `invoice`, `timesheet`, `ops`, `approve`, `report`, `anomaly`, `document` | ops |
| `kyc`, `compliance`, `onboard`, `verify`, `risk`, `sanctions`, `aml` | kyc |

The router scores all three buckets and picks the highest. On a tie, defaults to the first match.

**Exported function:**
```python
def run_workflow(
    task: str,
    instruction: str,
    document_content: str = "",
    client_data: dict = {}
) -> dict
```

---

## 7. Tools

### airtable_tool.py

| Function | Description |
|---|---|
| `add_lead(lead: dict)` | Creates record in Leads table |
| `get_all_leads()` | Returns all records |
| `update_lead_status(record_id, status)` | Updates Status field |
| `search_leads(query)` | Case-insensitive company name search |

**Airtable field mapping:**
```
"Company Name", "Industry", "Revenue Range", "Location",
"Contact Email", "Status", "Created At"
```

---

### gmail_tool.py

| Function | Description |
|---|---|
| `get_gmail_service()` | OAuth 2.0 auth — loads/refreshes token.json |
| `send_email(to, subject, body)` | Sends via Gmail API (MIMEText + base64) |
| `draft_followup_email(company, contact)` | Returns partnership email template string |

**Note:** If `token.json` does not exist, raises `RuntimeError` immediately instead of hanging. Run `python gmail_setup.py` once to generate it.

---

### slack_tool.py

| Function | Description |
|---|---|
| `send_alert(message, channel_id=None)` | Sends message with auto-emoji prefix |
| `send_ops_report(report_data: dict)` | Sends structured Block Kit report |

**Emoji logic:**
```
"flagged" / "risk"      → [ALERT]
"approved" / "complete" → [OK]
"pending" / "review"    → [PENDING]
default                 → [INFO]
```

---

### sanctions_tool.py

| Function | Description |
|---|---|
| `check_sanctions(name: str)` | Screens against OFAC + UK lists |

**Matching logic:**
- Loads OFAC SDN XML and UK CSV into memory cache (first call only)
- Fuzzy string matching with configurable threshold
- Returns: `sanctioned (bool)`, `confidence_score`, `matches`, `risk_action`

**Fallback chain:**
1. OpenSanctions API (if `OPENSANCTIONS_API_KEY` set)
2. Local OFAC XML (`data/sanctions/ofac_sdn.xml`)
3. Local UK CSV (`data/sanctions/uk_sanctions.csv`)

---

### risk_scoring.py

| Function | Description |
|---|---|
| `get_country_risk(country: str)` | Returns full AML risk profile |
| `is_high_risk_jurisdiction(country: str)` | Quick bool check |

**Embedded data:**
- FATF Black List (3 countries: North Korea, Iran, Myanmar)
- FATF Grey List (30+ jurisdictions)
- Basel AML Index 2023 (scores for 100+ countries, 0–10 scale)

---

### web_search_tool.py

| Function | Description |
|---|---|
| `search_companies(query, max_results=5)` | DuckDuckGo search → structured results |
| `research_company(company_name)` | Returns name, description, industry, URL |

---

### document_verification.py

| Function | Description |
|---|---|
| `verify_document(doc_type, image_path)` | OCR via Mindee API |

Extracts: name, date of birth, document number, expiry date, MRZ line, nationality. Only triggered if `document_image_path` is in `client_data`.

---

## 8. RAG Pipeline

### Ingestion (`rag/ingest.py`)

1. **initialize_chroma()** — creates `./chroma_db/` persistent store, collection `compliance_docs`
2. **ingest_text()** — chunks text (500 chars, 50 overlap) → embeds with `all-MiniLM-L6-v2` → upserts to ChromaDB
3. **ingest_sample_compliance_docs()** — ingests 5 baseline compliance docs on first startup if collection is empty

**Baseline docs (auto-generated if no PDFs present):**
- KYC Document Requirements
- AML Risk Assessment Criteria
- Data Privacy in KYC (GDPR)
- Client Onboarding Checklist
- Suspicious Activity Reporting

### Retrieval (`rag/retriever.py`)

```python
retrieve_context(query: str, n_results: int = 3) -> str
```

- Embeds query with same `all-MiniLM-L6-v2` model
- Runs cosine similarity search in ChromaDB
- Returns top N chunks as single concatenated string
- Handles empty collection gracefully (returns empty string)

### Adding Real Compliance PDFs

Place PDFs/TXTs in `rag/docs/`, delete `./chroma_db/`, restart server. It will re-ingest automatically.

Recommended documents:
- `fatf_40_recommendations.pdf` — from fatf-gafi.org
- `uk_mlr_2017.pdf` — from legislation.gov.uk
- `fca_sysc6.txt` — from handbook.fca.org.uk

---

## 9. API Reference

Base URL: `http://localhost:8000`

### GET /
```json
{
  "status": "OmniForce AI Workforce Running",
  "version": "1.0.0",
  "agents": ["sales", "ops", "kyc"],
  "docs": "/docs"
}
```

### GET /health
```json
{ "status": "healthy" }
```

### POST /run

**Request:**
```json
{
  "agent": "kyc",
  "instruction": "verify and check kyc documents for this client",
  "context": {
    "client_data": {
      "client_name": "Sarah Johnson",
      "email": "sarah.johnson@company.com",
      "documents": ["Passport", "Proof of Address", "Bank Statement"]
    }
  }
}
```

**Response:**
```json
{
  "success": true,
  "result": {
    "agent_used": "kyc",
    "status": "complete",
    "result": {
      "status": "complete",
      "client_name": "Sarah Johnson",
      "missing_docs": [],
      "risk_level": "Medium",
      "email_sent": false,
      "sanctions_result": {
        "sanctioned": false,
        "risk_action": "PASS — No sanctions match found."
      }
    }
  }
}
```

### POST /upload-invoice

Multipart form upload — PDF invoice for Ops Agent.

```bash
curl -X POST http://localhost:8000/upload-invoice \
  -F "file=@invoice.pdf" \
  -F "instruction=Process this invoice and check for anomalies"
```

### GET /leads

Returns all leads from Airtable CRM.

---

## 10. Environment Variables

```env
# Required
GROQ_API_KEY=               # console.groq.com
AIRTABLE_API_KEY=           # airtable.com/create/tokens
AIRTABLE_BASE_ID=           # From Airtable base URL
AIRTABLE_TABLE_NAME=Leads
SLACK_BOT_TOKEN=            # api.slack.com/apps — Bot Token (xoxb-)
SLACK_CHANNEL_ID=           # Channel ID (not name)
GMAIL_CREDENTIALS_PATH=credentials.json
GMAIL_TOKEN_PATH=token.json
SENDER_EMAIL=               # Gmail address matching credentials

# Optional — enhances KYC accuracy
OPENSANCTIONS_API_KEY=      # opensanctions.org/api (500 free/month)
MINDEE_API_KEY=             # platform.mindee.com (passport OCR)
```

---

## 11. Setup Guide

```bash
# 1. Clone the repo
git clone https://github.com/<your-username>/omniforce-ai-workforce.git
cd omniforce-ai-workforce

# 2. Create virtual environment (Python 3.10-3.12 recommended)
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
copy .env.example .env
# Open .env and fill in all API keys

# 5. Download sanctions data (OFAC + UK lists)
python scripts/download_data.py

# 6. Set up Gmail OAuth (one time only)
python gmail_setup.py
# Browser opens → select Google account → Allow → token.json created

# 7. Start the backend server
python -m uvicorn main:app --reload --port 8000

# 8. Start Streamlit UI (new terminal)
streamlit run demo/app.py
```

**Server startup output (expected):**
```
[OmniForce] AI Workforce starting up...
[OmniForce] ChromaDB ready: 890 chunks loaded
[OmniForce] Sanctions data preloaded
INFO: Application startup complete.
```

---

## 12. Gmail OAuth Setup

Gmail requires a one-time OAuth authentication before emails can be sent.

**Prerequisites:**
1. Google Cloud project with Gmail API enabled
2. OAuth 2.0 credentials (Desktop app type) downloaded as `credentials.json`
3. Your email added as a Test User in Google Cloud Console → APIs & Services → OAuth consent screen → Audience

**Steps:**
```bash
python gmail_setup.py
```
- Browser opens automatically
- Select your Google account
- Click Allow
- Window closes — `token.json` created

**If "This site can't be reached" appears:**
- Ensure you're on port 8080 (gmail_setup.py uses `port=8080`)

**If Google account doesn't appear:**
- Go to console.cloud.google.com → APIs & Services → OAuth consent screen → Audience → Add your email as test user

Once `token.json` exists, all email functionality works automatically. Token auto-refreshes when expired.

---

## 13. Test Results

Automated test suite: `test_kyc_agent.py`

Run: `python test_kyc_agent.py` (server must be running)

| Test | Client | Scenario | Status | Time |
|---|---|---|---|---|
| Test 1 | Sarah Johnson | All docs present, clean client | PASS | ~5s |
| Test 2 | James Mitchell | Missing docs, email trigger | PASS | ~10s |
| Test 3 | Emma Williams | Full onboarding pipeline | PASS | ~6s |

**Test 1 expected output:**
```json
{ "status": "complete", "missing_docs": [], "email_sent": false, "risk_level": "Medium" }
```

**Test 2 expected output:**
```json
{
  "status": "complete",
  "missing_docs": ["Proof of Address", "Bank Statement"],
  "email_sent": true
}
```

**Test 3 expected output:**
```json
{
  "status": "complete",
  "missing_docs": [],
  "welcome_email_sent": true,
  "onboarding_report": "...full Llama-generated report..."
}
```

---

## 14. Data Sources

| Dataset | Source | Size | Update Frequency |
|---|---|---|---|
| OFAC SDN List | ofac.treasury.gov | 28 MB | Weekly |
| UK HM Treasury Sanctions | sanctionslist.fcdo.gov.uk | 47 MB | Weekly |
| FATF Black List | Embedded in risk_scoring.py | — | Quarterly (manual) |
| FATF Grey List | Embedded in risk_scoring.py | — | Quarterly (manual) |
| Basel AML Index 2023 | Embedded in risk_scoring.py | — | Annual (manual) |
| Compliance RAG Docs | rag/docs/ | Variable | Manual |

---

## 15. Known Limitations

| Limitation | Detail | Workaround |
|---|---|---|
| Gmail OAuth | Requires one-time browser setup | Run `python gmail_setup.py` |
| FATF/Basel data | Embedded, not live | Update `risk_scoring.py` quarterly |
| Mindee OCR | Optional, needs API key | Works without it — OCR step skipped |
| OpenSanctions API | 500 free req/month | Falls back to local OFAC/UK XML files |
| Python 3.13+ | LangChain Pydantic V1 warning | Use Python 3.10–3.12 for clean run |
| country field | If not provided, defaults to Medium risk | Always pass `country` in client_data for accurate risk |
| Streamlit UI | Not tested in this session | Use API directly or Streamlit separately |
