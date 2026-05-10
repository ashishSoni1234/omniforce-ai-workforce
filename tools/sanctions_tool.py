"""
Sanctions screening using local data files — no API key required.

Primary:   data/sanctions/ofac_sdn.xml   (US Treasury OFAC SDN list, ~28 MB)
Secondary: data/sanctions/uk_sanctions.csv (UK HM Treasury consolidated list, ~48 MB)

Both files are downloaded by: python scripts/download_data.py
No internet connection or API key needed at runtime.
"""

import csv
import logging
import xml.etree.ElementTree as ET
from pathlib import Path

logger = logging.getLogger(__name__)

ROOT = Path(__file__).parent.parent
OFAC_XML_PATH = ROOT / "data" / "sanctions" / "ofac_sdn.xml"
UK_CSV_PATH = ROOT / "data" / "sanctions" / "uk_sanctions.csv"

# UK CSV name columns (from HM Treasury consolidated list format)
_UK_NAME_COLS = ["Name 6", "Name 1", "Name 2", "Name 3", "Name 4", "Name 5"]

# In-memory cache — parsed once on first call, reused for all subsequent requests
_OFAC_CACHE: list[dict] | None = None
_UK_CACHE: list[dict] | None = None


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def _name_match(query: str, candidate: str) -> float:
    """Return match score 0.0–1.0 between query and candidate name."""
    q = _normalize(query)
    c = _normalize(candidate)
    if not q or not c:
        return 0.0
    if q == c:
        return 1.0
    if q in c or c in q:
        # Require meaningful length and proportionality to avoid false positives
        # e.g. "J" in "James Mitchell" or "MIT" in "Mitchell" should NOT match
        min_len = min(len(q), len(c))
        max_len = max(len(q), len(c))
        if min_len >= 6 and min_len / max_len >= 0.6:
            return 0.90
    # Token overlap score
    q_tokens = set(q.split())
    c_tokens = set(c.split())
    if not q_tokens or not c_tokens:
        return 0.0
    overlap = len(q_tokens & c_tokens) / max(len(q_tokens), len(c_tokens))
    return round(overlap, 3)


def _load_ofac_cache() -> list[dict]:
    """Parse OFAC SDN XML once and cache all entries in memory."""
    global _OFAC_CACHE
    if _OFAC_CACHE is not None:
        return _OFAC_CACHE

    if not OFAC_XML_PATH.exists():
        logger.warning("[Sanctions] OFAC XML not found — run: python scripts/download_data.py")
        _OFAC_CACHE = []
        return _OFAC_CACHE

    logger.info("[Sanctions] Loading OFAC XML into memory (one-time)...")
    entries = []
    try:
        tree = ET.parse(OFAC_XML_PATH)
        root = tree.getroot()
        for entry in root.iter():
            if not entry.tag.endswith("sdnEntry"):
                continue
            last = first = sdn_type = uid = ""
            for child in entry:
                tag = child.tag.split("}")[-1]
                if tag == "lastName":
                    last = child.text or ""
                elif tag == "firstName":
                    first = child.text or ""
                elif tag == "sdnType":
                    sdn_type = child.text or ""
                elif tag == "uid":
                    uid = child.text or ""
            full = f"{first} {last}".strip()
            if full:
                entries.append({"name": full, "uid": uid, "type": sdn_type})
    except ET.ParseError as exc:
        logger.error("[Sanctions] OFAC XML parse error: %s", exc)

    _OFAC_CACHE = entries
    logger.info("[Sanctions] OFAC cache ready — %d entries", len(entries))
    return _OFAC_CACHE


def _load_uk_cache() -> list[dict]:
    """Parse UK CSV once and cache all entries in memory."""
    global _UK_CACHE
    if _UK_CACHE is not None:
        return _UK_CACHE

    if not UK_CSV_PATH.exists():
        logger.warning("[Sanctions] UK CSV not found — run: python scripts/download_data.py")
        _UK_CACHE = []
        return _UK_CACHE

    logger.info("[Sanctions] Loading UK sanctions CSV into memory (one-time)...")
    entries = []
    try:
        with open(UK_CSV_PATH, encoding="utf-8-sig", errors="replace") as f:
            f.readline()
            reader = csv.DictReader(f)
            for row in reader:
                names = [row.get(col, "").strip() for col in _UK_NAME_COLS if row.get(col, "").strip()]
                if names:
                    entries.append({
                        "names": names,
                        "uid": row.get("Unique ID", ""),
                        "regime": row.get("Regime Name", ""),
                        "designation": row.get("Designation Type", ""),
                    })
    except Exception as exc:
        logger.error("[Sanctions] UK CSV parse error: %s", exc)

    _UK_CACHE = entries
    logger.info("[Sanctions] UK cache ready — %d entries", len(entries))
    return _UK_CACHE


def _check_via_ofac_xml(name: str) -> list[dict]:
    """Screen name against cached OFAC SDN entries."""
    matches = []
    for entry in _load_ofac_cache():
        score = _name_match(name, entry["name"])
        if score >= 0.80:
            matches.append({
                "name": entry["name"],
                "score": score,
                "uid": entry["uid"],
                "type": entry["type"],
                "datasets": ["OFAC SDN"],
            })
        if len(matches) >= 10:
            break
    return matches


def _check_via_uk_csv(name: str) -> list[dict]:
    """Screen name against cached UK HM Treasury entries."""
    matches = []
    for entry in _load_uk_cache():
        best_score = 0.0
        best_name = ""
        for candidate in entry["names"]:
            score = _name_match(name, candidate)
            if score > best_score:
                best_score = score
                best_name = candidate
        if best_score >= 0.80:
            matches.append({
                "name": best_name,
                "score": best_score,
                "uid": entry["uid"],
                "regime": entry["regime"],
                "designation": entry["designation"],
                "datasets": ["UK HM Treasury Sanctions"],
            })
        if len(matches) >= 10:
            break
    return matches


def check_sanctions(name: str) -> dict:
    """
    Screen a name against OFAC SDN and UK HM Treasury sanctions lists (local files).

    No API key or internet connection required.

    Args:
        name: Person or entity name to screen.

    Returns:
        dict with keys: sanctioned (bool), confidence_score, source, matches, risk_action
    """
    if not name or not name.strip():
        return {"sanctioned": False, "error": "Empty name provided"}

    logger.info("[Sanctions] Screening: %s", name)

    ofac_matches = _check_via_ofac_xml(name)
    uk_matches = _check_via_uk_csv(name)

    all_matches = ofac_matches + uk_matches
    all_matches.sort(key=lambda m: m["score"], reverse=True)

    sanctioned = bool(all_matches)
    top_score = all_matches[0]["score"] if all_matches else 0.0

    sources = []
    if ofac_matches:
        sources.append("OFAC SDN XML (local)")
    if uk_matches:
        sources.append("UK HM Treasury CSV (local)")
    source = " + ".join(sources) if sources else "OFAC SDN + UK Sanctions (local)"

    result = {
        "sanctioned": sanctioned,
        "confidence_score": round(top_score, 3),
        "source": source,
        "matches": all_matches[:5],
    }

    if sanctioned:
        result["risk_action"] = "BLOCK — Do not onboard. File SAR if appropriate."
        result["risk_level"] = "High"
    else:
        result["risk_action"] = "PASS — No sanctions match found. Proceed with standard KYC."
        result["risk_level"] = "Low"

    logger.info(
        "[Sanctions] Result for '%s': sanctioned=%s | top_score=%.2f | source=%s",
        name, sanctioned, top_score, source,
    )
    return result
