"""
Download and verify all real compliance datasets for OmniForce AML/KYC system.

Run once before starting the server:
    python scripts/download_data.py

What it downloads:
    rag/docs/fatf_40_recommendations.pdf   -- FATF 40 Recommendations
    rag/docs/uk_mlr_2017.pdf               -- UK Money Laundering Regulations 2017
    rag/docs/fca_sysc6.txt                 -- FCA SYSC 6 Handbook (scraped HTML)
    data/sanctions/ofac_sdn.xml            -- OFAC SDN List (US Treasury)
    data/sanctions/uk_sanctions.csv        -- UK HM Treasury Consolidated Sanctions
"""

import logging
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).parent.parent
RAG_DOCS = ROOT / "rag" / "docs"
SANCTIONS_DIR = ROOT / "data" / "sanctions"

for d in (RAG_DOCS, SANCTIONS_DIR):
    d.mkdir(parents=True, exist_ok=True)

TIMEOUT = 30
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}
MIN_VALID_SIZE = 500  # bytes — anything smaller is treated as failed/empty


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def download_file(url: str, dest: Path, label: str) -> bool:
    """Download a URL to dest. Returns True only if file is > MIN_VALID_SIZE bytes."""
    if dest.exists() and dest.stat().st_size > MIN_VALID_SIZE:
        logger.info("[SKIP] %s already exists (%d bytes)", label, dest.stat().st_size)
        return True

    logger.info("[DOWN] %s from %s", label, url)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT, stream=True)
        resp.raise_for_status()

        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)

        size = dest.stat().st_size
        if size < MIN_VALID_SIZE:
            logger.warning("[FAIL] %s downloaded but only %d bytes (likely redirect/error page)", label, size)
            dest.unlink(missing_ok=True)
            return False

        logger.info("[OK] %s -> %s (%d bytes)", label, dest.name, size)
        return True

    except requests.exceptions.HTTPError as exc:
        logger.error("[FAIL] HTTP %s for %s", exc.response.status_code, label)
    except requests.exceptions.Timeout:
        logger.error("[FAIL] Timeout: %s", label)
    except Exception as exc:
        logger.error("[FAIL] %s: %s", label, exc)

    dest.unlink(missing_ok=True)
    return False


def scrape_to_text(url: str, dest: Path, label: str, min_chars: int = 1000) -> bool:
    """Scrape a web page, extract readable text, save as .txt. Returns True on success."""
    if dest.exists() and dest.stat().st_size > min_chars:
        logger.info("[SKIP] %s already exists (%d bytes)", label, dest.stat().st_size)
        return True

    logger.info("[SCRAPE] %s from %s", label, url)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        clean = "\n".join(lines)

        if len(clean) < min_chars:
            logger.warning("[FAIL] Scraped text too short (%d chars) for %s — likely JS-rendered", len(clean), label)
            return False

        dest.write_text(clean, encoding="utf-8")
        logger.info("[OK] %s -> %s (%d chars)", label, dest.name, len(clean))
        return True
    except Exception as exc:
        logger.error("[FAIL] Scrape %s: %s", label, exc)
        return False


def find_uk_sanctions_csv_url() -> str | None:
    """
    Scrape the UK gov.uk sanctions page to find the current CSV download URL.
    The direct URL changes with each update; the page always links to the latest.
    """
    page_url = "https://www.gov.uk/government/publications/the-uk-sanctions-list"
    logger.info("[SCRAPE] Finding UK sanctions CSV link from %s", page_url)
    try:
        resp = requests.get(page_url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "consolidated" in href.lower() and href.endswith(".csv"):
                if href.startswith("http"):
                    return href
                return "https://www.gov.uk" + href

        # Also check for any assets.publishing.service.gov.uk CSV links
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "assets.publishing.service.gov.uk" in href and href.endswith(".csv"):
                return href

        logger.warning("[WARN] Could not find CSV link on UK sanctions page")
        return None
    except Exception as exc:
        logger.error("[FAIL] Could not scrape UK sanctions page: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Dataset definitions
# ---------------------------------------------------------------------------

DOWNLOADS: list[dict] = [
    {
        "label": "FATF 40 Recommendations (PDF)",
        "type": "file",
        "urls": [
            "https://www.fatf-gafi.org/content/dam/fatf-gafi/recommendations/FATF%20Recommendations%202012.pdf.coredownload.inline.pdf",
            "https://www.fatf-gafi.org/media/fatf/documents/recommendations/pdfs/FATF_Recommendations.pdf",
        ],
        "dest": RAG_DOCS / "fatf_40_recommendations.pdf",
        "manual": (
            "1. Go to: https://www.fatf-gafi.org/en/publications/Fatfrecommendations/Fatf-recommendations.html\n"
            "   2. Click 'Download' or 'Read online' -> Download PDF\n"
            "   3. Save file to: rag/docs/fatf_40_recommendations.pdf"
        ),
    },
    {
        "label": "UK Money Laundering Regulations 2017 (PDF)",
        "type": "file",
        "urls": [
            "https://www.legislation.gov.uk/uksi/2017/692/pdfs/uksi_20170692_en.pdf",
        ],
        "dest": RAG_DOCS / "uk_mlr_2017.pdf",
        "manual": (
            "1. Go to: https://www.legislation.gov.uk/uksi/2017/692/contents/made\n"
            "   2. Click 'Print / Save as PDF' or use browser Print -> Save as PDF\n"
            "   3. Save file to: rag/docs/uk_mlr_2017.pdf"
        ),
    },
    {
        "label": "FCA SYSC 6 Handbook (web scrape)",
        "type": "scrape",
        "urls": [
            "https://www.handbook.fca.org.uk/handbook/SYSC/6/?view=chapter",
        ],
        "dest": RAG_DOCS / "fca_sysc6.txt",
        "manual": (
            "1. Go to: https://www.handbook.fca.org.uk/handbook/SYSC/6/\n"
            "   2. Press Ctrl+A, Ctrl+C to copy all text\n"
            "   3. Paste into a new file: rag/docs/fca_sysc6.txt\n"
            "   (The FCA site uses heavy JavaScript — automated scraping is blocked)"
        ),
    },
    {
        "label": "OFAC SDN XML (US Treasury)",
        "type": "file",
        "urls": [
            "https://ofac.treasury.gov/downloads/sdn.xml",
            "https://www.treasury.gov/ofac/downloads/sdn.xml",
        ],
        "dest": SANCTIONS_DIR / "ofac_sdn.xml",
        "manual": (
            "1. Go to: https://ofac.treasury.gov/specially-designated-nationals-and-blocked-persons-list-sdn-human-readable-lists\n"
            "   2. Download 'SDN List in XML format'\n"
            "   3. Save file to: data/sanctions/ofac_sdn.xml"
        ),
    },
    {
        "label": "UK FCDO Sanctions (CSV)",
        "type": "file",
        "urls": [
            "https://sanctionslist.fcdo.gov.uk/docs/UK-Sanctions-List.csv",
        ],
        "dest": SANCTIONS_DIR / "uk_sanctions.csv",
        "manual": (
            "1. Go to: https://www.gov.uk/government/publications/the-uk-sanctions-list\n"
            "   2. Download 'UK-Sanctions-List.csv'\n"
            "   3. Save file to: data/sanctions/uk_sanctions.csv"
        ),
    },
]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_downloads() -> dict:
    results = {"succeeded": [], "failed": []}

    for item in DOWNLOADS:
        label = item["label"]
        dest: Path = item["dest"]
        succeeded = False

        if item["type"] == "uk_sanctions":
            # Special case: find URL dynamically
            csv_url = find_uk_sanctions_csv_url()
            if csv_url:
                succeeded = download_file(csv_url, dest, label)
            else:
                logger.warning("[FAIL] Could not find UK sanctions CSV URL automatically")

        else:
            for url in item["urls"]:
                if item["type"] == "file":
                    succeeded = download_file(url, dest, label)
                else:
                    succeeded = scrape_to_text(url, dest, label)

                if succeeded:
                    break
                time.sleep(1)

        if succeeded:
            results["succeeded"].append({"label": label, "path": str(dest), "size": dest.stat().st_size})
        else:
            results["failed"].append({
                "label": label,
                "dest": str(dest),
                "manual": item["manual"],
            })

    return results


def print_summary(results: dict):
    sep = "=" * 65
    print(f"\n{sep}")
    print("  DOWNLOAD SUMMARY")
    print(sep)

    print(f"\nSUCCEEDED ({len(results['succeeded'])}):")
    for s in results["succeeded"]:
        size_kb = s["size"] // 1024
        print(f"  [OK] {s['label']} ({size_kb} KB) -> {s['path']}")

    if results["failed"]:
        print(f"\nFAILED ({len(results['failed'])}) -- Manual steps required:")
        for idx, f in enumerate(results["failed"], 1):
            print(f"\n  [{idx}] {f['label']}")
            print(f"       Save to  : {f['dest']}")
            print(f"       Steps    :")
            print(f"       {f['manual']}")

    print(f"\n{sep}")
    if not results["failed"]:
        print("  All datasets downloaded successfully!")
    else:
        print(f"  {len(results['failed'])} dataset(s) need manual download (see above).")
    print(sep + "\n")


def download_sanctions_data():
    """Download only OFAC + UK sanctions files. Called from main.py startup on cloud deployments."""
    sanctions_items = [d for d in DOWNLOADS if d["dest"].parent == SANCTIONS_DIR]
    for item in sanctions_items:
        for url in item["urls"]:
            if download_file(url, item["dest"], item["label"]):
                break
            time.sleep(1)


if __name__ == "__main__":
    logger.info("OmniForce compliance dataset downloader starting...")
    results = run_downloads()
    print_summary(results)
    sys.exit(0 if not results["failed"] else 1)
