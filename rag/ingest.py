"""
RAG ingestion pipeline for OmniForce compliance documents.

Loads PDFs and .txt files from rag/docs/, chunks them, embeds with
sentence-transformers, and stores in ChromaDB.

Fallback: if rag/docs/ has no files, ingest built-in baseline compliance text
so the KYC agent always has some context to work with.
"""

import logging
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

CHROMA_PATH = "./chroma_db"
COLLECTION_NAME = "compliance_docs"
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
DOCS_DIR = Path(__file__).parent / "docs"

_embedder = None
_chroma_collection = None


def _get_embedder() -> SentenceTransformer:
    global _embedder
    if _embedder is None:
        logger.info("[RAG] Loading embedding model: %s", EMBED_MODEL)
        _embedder = SentenceTransformer(EMBED_MODEL)
        logger.info("[RAG] Embedding model loaded")
    return _embedder


def _chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    chunks = []
    start = 0
    while start < len(text):
        chunks.append(text[start: start + chunk_size])
        start += chunk_size - overlap
    return chunks


# ---------------------------------------------------------------------------
# Public extraction helpers
# ---------------------------------------------------------------------------

def extract_pdf_text(pdf_path: Path) -> str:
    """
    Extract plain text from a PDF using PyMuPDF (fitz).

    Returns empty string if extraction fails (non-crashing).
    """
    try:
        import fitz  # PyMuPDF
        text_parts = []
        with fitz.open(str(pdf_path)) as doc:
            for page in doc:
                text_parts.append(page.get_text("text"))
        text = "\n".join(text_parts).strip()
        logger.info("[RAG] Extracted %d chars from PDF: %s", len(text), pdf_path.name)
        return text
    except ImportError:
        logger.error("[RAG] PyMuPDF not installed — run: pip install pymupdf")
        return ""
    except Exception as exc:
        logger.error("[RAG] Failed to extract PDF %s: %s", pdf_path.name, exc)
        return ""


def extract_text_file(txt_path: Path) -> str:
    """Read a plain-text or scraped compliance document."""
    try:
        text = txt_path.read_text(encoding="utf-8", errors="ignore").strip()
        logger.info("[RAG] Read %d chars from text file: %s", len(text), txt_path.name)
        return text
    except Exception as exc:
        logger.error("[RAG] Failed to read text file %s: %s", txt_path.name, exc)
        return ""


def load_all_documents() -> list[dict]:
    """
    Scan rag/docs/ and return a list of {doc_id, text, metadata} dicts.

    Supports: .pdf, .txt
    Falls back to built-in baseline docs if folder is empty.
    """
    documents = []

    if DOCS_DIR.exists():
        pdf_files = list(DOCS_DIR.glob("*.pdf"))
        txt_files = list(DOCS_DIR.glob("*.txt"))
        all_files = pdf_files + txt_files

        for path in all_files:
            if path.suffix.lower() == ".pdf":
                text = extract_pdf_text(path)
                source_type = "pdf"
            else:
                text = extract_text_file(path)
                source_type = "txt"

            if len(text) < 100:
                logger.warning("[RAG] Skipping %s — too short (%d chars)", path.name, len(text))
                continue

            doc_id = path.stem.lower().replace(" ", "_").replace("-", "_")
            documents.append({
                "doc_id": doc_id,
                "text": text,
                "metadata": {
                    "source": path.name,
                    "type": source_type,
                    "category": "compliance",
                },
            })
            logger.info("[RAG] Loaded document: %s (%d chars)", path.name, len(text))
    else:
        logger.warning("[RAG] rag/docs/ directory not found")

    if not documents:
        logger.warning("[RAG] No real compliance docs found — loading built-in baseline")
        documents = _load_baseline_docs()

    return documents


# ---------------------------------------------------------------------------
# ChromaDB operations
# ---------------------------------------------------------------------------

def initialize_chroma() -> chromadb.Collection:
    global _chroma_collection
    if _chroma_collection is not None:
        return _chroma_collection
    logger.info("[RAG] Initialising ChromaDB at %s", CHROMA_PATH)
    try:
        client = chromadb.PersistentClient(path=CHROMA_PATH)
        _chroma_collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info("[RAG] Collection '%s' ready — %d chunks", COLLECTION_NAME, _chroma_collection.count())
        return _chroma_collection
    except Exception as exc:
        raise RuntimeError(f"[RAG] Failed to initialise ChromaDB: {exc}") from exc


def ingest_text(text: str, doc_id: str, metadata: dict) -> bool:
    """Chunk, embed, and upsert a single document into ChromaDB."""
    logger.info("[RAG] Ingesting: %s", doc_id)
    try:
        collection = initialize_chroma()
        embedder = _get_embedder()
        chunks = _chunk_text(text)

        chunk_ids = [f"{doc_id}_chunk_{i}" for i in range(len(chunks))]
        embeddings = embedder.encode(chunks).tolist()
        chunk_metadata = [{**metadata, "doc_id": doc_id, "chunk_index": i} for i in range(len(chunks))]

        collection.upsert(
            ids=chunk_ids,
            documents=chunks,
            embeddings=embeddings,
            metadatas=chunk_metadata,
        )
        logger.info("[RAG] Ingested '%s' — %d chunks", doc_id, len(chunks))
        return True
    except Exception as exc:
        logger.error("[RAG] Failed to ingest '%s': %s", doc_id, exc)
        return False


def ingest_all_documents() -> int:
    """
    Main entry point: load all docs from rag/docs/ and ingest into ChromaDB.

    Returns number of documents successfully ingested.
    """
    documents = load_all_documents()
    success = 0
    for doc in documents:
        if ingest_text(doc["text"], doc["doc_id"], doc["metadata"]):
            success += 1
    logger.info("[RAG] Ingestion complete — %d/%d documents", success, len(documents))
    return success


# Keep old name as alias so existing startup code still works
def ingest_sample_compliance_docs() -> int:
    """Alias for ingest_all_documents() — backward-compatible entry point."""
    return ingest_all_documents()


# ---------------------------------------------------------------------------
# Built-in baseline compliance text (fallback only)
# ---------------------------------------------------------------------------

def _load_baseline_docs() -> list[dict]:
    """
    Minimal built-in compliance text used ONLY when no real PDFs are present.
    Replace with real documents by running: python scripts/download_data.py
    """
    baseline = [
        {
            "doc_id": "kyc_requirements_baseline",
            "text": """KYC Requirements — Financial Services Baseline
Required documents for individual clients:
1. Government-issued photo ID (Passport, National ID, or Driver's Licence)
2. Proof of Address (utility bill or bank statement dated within 3 months)
3. Bank Statement (last 3 months)
4. Source of Funds declaration

Verification: All documents must be certified or verified against originals.
Ongoing monitoring: Refresh every 12 months for high-risk, 3 years medium-risk, 5 years low-risk.

Enhanced Due Diligence (EDD) triggers: PEPs, high-risk jurisdictions, complex structures.
Simplified Due Diligence (SDD): regulated firms, listed companies, government bodies.""",
            "metadata": {"source": "baseline", "type": "txt", "category": "kyc"},
        },
        {
            "doc_id": "aml_rules_baseline",
            "text": """AML Rules — Baseline Reference
Under the Money Laundering Regulations 2017 and Proceeds of Crime Act 2002.

Red flags requiring Enhanced Due Diligence:
- Cash transactions exceeding £10,000
- Transactions with FATF-blacklisted jurisdictions
- Unusual patterns inconsistent with client profile
- Rapid fund movements through multiple accounts
- Clients reluctant to provide source of funds

SAR Reporting: File with National Crime Agency (NCA) on suspicion of money laundering.
Tipping off the subject is a criminal offence.

Thresholds:
- £1,000–£9,999: Standard monitoring
- £10,000–£49,999: Enhanced monitoring, manager approval
- £50,000+: Full EDD, senior compliance officer sign-off

Record keeping: Minimum 5 years post-relationship end.""",
            "metadata": {"source": "baseline", "type": "txt", "category": "aml"},
        },
        {
            "doc_id": "risk_assessment_baseline",
            "text": """Risk Assessment Criteria — Client Classification

LOW RISK (Standard Due Diligence):
- Private individuals with verifiable employment income
- Established UK businesses with transparent ownership
- Regulated financial institutions
- Listed companies on reputable exchanges

MEDIUM RISK (Customer Due Diligence):
- Non-face-to-face / fully digital onboarding
- FATF grey-list country clients
- Complex but clear ownership structures

HIGH RISK (Enhanced Due Diligence mandatory):
- Politically Exposed Persons (PEPs) and family
- FATF black/grey list jurisdictions
- Cryptocurrency, gambling, arms, precious metals industries
- Anonymous or bearer share structures
- Adverse media hits

Scoring: 0–30 Low | 31–60 Medium | 61–100 High
Board approval required for risk score > 80.""",
            "metadata": {"source": "baseline", "type": "txt", "category": "risk"},
        },
        {
            "doc_id": "onboarding_checklist_baseline",
            "text": """Client Onboarding Checklist

Step 1: Initial Screening
- Screen name against OFAC, HM Treasury, UN sanctions lists
- Check for PEP status
- Verify not on internal blacklist

Step 2: Document Collection
- Collect required KYC documents
- Verify authenticity (certification or digital verification)
- Obtain Source of Funds / Source of Wealth declaration
- Collect signed terms and conditions

Step 3: Risk Assessment
- Complete client risk assessment
- Classify as Low/Medium/High risk
- Apply SDD / CDD / EDD as appropriate
- Obtain management approval for high-risk clients

Step 4: Account Setup
- Create client record in CRM
- Set compliance monitoring rules
- Configure transaction limits

Step 5: Ongoing Monitoring
- Schedule KYC review date based on risk level
- Set up automated transaction monitoring""",
            "metadata": {"source": "baseline", "type": "txt", "category": "onboarding"},
        },
    ]
    return baseline
