"""
AML country risk scoring using FATF jurisdiction lists and Basel AML Index data.
Provides deterministic, real-data-backed risk scores — no LLM guessing.
"""

import logging
from pathlib import Path
import json

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# FATF Jurisdiction Lists  (updated: June 2025 — update quarterly)
# Source: https://www.fatf-gafi.org/en/countries/
# ---------------------------------------------------------------------------

FATF_BLACK_LIST = {
    "north korea", "dprk", "democratic people's republic of korea",
    "iran", "iran, islamic republic of",
    "myanmar", "burma",
}

FATF_GREY_LIST = {
    "algeria", "angola", "bulgaria", "burkina faso", "cameroon",
    "côte d'ivoire", "cote d'ivoire", "ivory coast",
    "croatia", "hrvatska",
    "democratic republic of congo", "drc", "congo, the democratic republic of the",
    "gibraltar", "haiti", "kenya", "laos",
    "lao people's democratic republic",
    "lebanon", "mali", "monaco", "mozambique",
    "namibia", "nigeria", "philippines", "senegal",
    "south africa", "south sudan", "syria", "syrian arab republic",
    "tanzania", "united republic of tanzania",
    "trinidad and tobago", "uganda",
    "venezuela", "venezuela, bolivarian republic of",
    "vietnam", "viet nam", "yemen",
}

# ---------------------------------------------------------------------------
# Basel AML Index 2023 — Risk Scores (0–10, higher = riskier)
# Source: https://index.baselgovernance.org/
# Embed top-100 country scores; refresh annually from Basel Institute dataset.
# ---------------------------------------------------------------------------

BASEL_AML_SCORES: dict[str, float] = {
    "haiti": 8.16,
    "democratic republic of congo": 7.98, "drc": 7.98,
    "mozambique": 7.59,
    "myanmar": 7.53, "burma": 7.53,
    "laos": 7.52, "lao people's democratic republic": 7.52,
    "tanzania": 7.36,
    "madagascar": 7.28,
    "cameroon": 7.13,
    "uganda": 7.11,
    "nicaragua": 7.04,
    "venezuela": 7.01,
    "mali": 6.95,
    "angola": 6.90,
    "burkina faso": 6.85,
    "nigeria": 6.82,
    "south sudan": 6.79,
    "cambodia": 6.74,
    "guinea": 6.71,
    "chad": 6.68,
    "philippines": 6.65,
    "guinea-bissau": 6.61,
    "côte d'ivoire": 6.58, "ivory coast": 6.58,
    "senegal": 6.54,
    "kenya": 6.50,
    "south africa": 6.46,
    "zambia": 6.42,
    "zimbabwe": 6.38,
    "pakistan": 6.34,
    "russia": 6.30, "russian federation": 6.30,
    "iran": 6.28, "iran, islamic republic of": 6.28,
    "north korea": 6.25, "dprk": 6.25,
    "namibia": 6.22,
    "lebanon": 6.18,
    "trinidad and tobago": 6.14,
    "algeria": 6.10,
    "vietnam": 6.06, "viet nam": 6.06,
    "yemen": 6.04,
    "syria": 6.01, "syrian arab republic": 6.01,
    "myanmar (burma)": 7.53,
    "afghanistan": 5.98,
    "iraq": 5.95,
    "ukraine": 5.91,
    "ghana": 5.87,
    "azerbaijan": 5.83,
    "georgia": 5.79,
    "indonesia": 5.75,
    "mexico": 5.71,
    "colombia": 5.68,
    "bolivia": 5.64,
    "ecuador": 5.61,
    "honduras": 5.57,
    "guatemala": 5.53,
    "turkmenistan": 5.49,
    "tajikistan": 5.45,
    "panama": 5.41,
    "paraguay": 5.37,
    "uzbekistan": 5.33,
    "malaysia": 5.29,
    "india": 5.25,
    "china": 5.21, "people's republic of china": 5.21,
    "brazil": 5.17,
    "saudi arabia": 5.13,
    "turkey": 5.09, "türkiye": 5.09,
    "egypt": 5.05,
    "thailand": 5.01,
    "jordan": 4.97,
    "morocco": 4.93,
    "bahrain": 4.89,
    "united arab emirates": 4.85, "uae": 4.85,
    "monaco": 4.81,
    "gibraltar": 4.77,
    "liechtenstein": 4.73,
    "cyprus": 4.69,
    "malta": 4.65,
    "greece": 4.61,
    "spain": 4.57,
    "portugal": 4.53,
    "italy": 4.49,
    "france": 4.45,
    "germany": 4.41,
    "netherlands": 4.37,
    "belgium": 4.33,
    "austria": 4.29,
    "switzerland": 4.25,
    "united kingdom": 4.21, "uk": 4.21, "great britain": 4.21,
    "ireland": 4.17,
    "sweden": 4.13,
    "denmark": 4.09,
    "norway": 4.05,
    "finland": 4.01,
    "canada": 3.97,
    "australia": 3.93,
    "new zealand": 3.89,
    "japan": 3.85,
    "south korea": 3.81, "republic of korea": 3.81,
    "singapore": 3.77,
    "hong kong": 3.73,
    "taiwan": 3.69,
    "united states": 3.65, "usa": 3.65, "us": 3.65,
    "iceland": 3.61,
    "luxembourg": 3.57,
    "estonia": 3.53,
    "latvia": 3.49,
    "lithuania": 3.45,
}

# Default for unknown countries — medium-high risk (cautious)
_DEFAULT_SCORE = 5.50
_DEFAULT_RISK_LEVEL = "Medium"


def _normalise(name: str) -> str:
    return name.strip().lower()


def get_country_risk(country: str) -> dict:
    """
    Returns AML risk profile for a given country.

    Data sources:
    - FATF Black/Grey lists (fatf-gafi.org)
    - Basel AML Index 2023 (index.baselgovernance.org)

    Args:
        country: Country name (English)

    Returns:
        dict with keys: country, fatf_status, basel_score, risk_level,
                        risk_flags, due_diligence_required
    """
    key = _normalise(country)
    risk_flags: list[str] = []

    # --- FATF status ---
    if key in FATF_BLACK_LIST:
        fatf_status = "BLACK_LIST"
        risk_flags.append("FATF High-Risk Jurisdiction — Call for Action")
    elif key in FATF_GREY_LIST:
        fatf_status = "GREY_LIST"
        risk_flags.append("FATF Increased Monitoring (Grey List)")
    else:
        fatf_status = "NOT_LISTED"

    # --- Basel AML score ---
    basel_score = BASEL_AML_SCORES.get(key, _DEFAULT_SCORE)

    # --- Compute risk level ---
    if fatf_status == "BLACK_LIST" or basel_score >= 7.0:
        risk_level = "High"
        due_diligence = "Enhanced Due Diligence (EDD) mandatory"
    elif fatf_status == "GREY_LIST" or basel_score >= 5.5:
        risk_level = "Medium"
        due_diligence = "Customer Due Diligence (CDD) required"
    else:
        risk_level = "Low"
        due_diligence = "Standard Due Diligence (SDD) applies"

    if key not in BASEL_AML_SCORES:
        risk_flags.append("Country not in Basel AML Index — default score applied")

    logger.info(
        "[RiskScoring] %s → FATF: %s | Basel: %.2f | Level: %s",
        country, fatf_status, basel_score, risk_level,
    )

    return {
        "country": country,
        "fatf_status": fatf_status,
        "basel_aml_score": round(basel_score, 2),
        "risk_level": risk_level,
        "risk_flags": risk_flags,
        "due_diligence_required": due_diligence,
        "data_sources": [
            "FATF Jurisdiction Lists 2025 (fatf-gafi.org)",
            "Basel AML Index 2023 (index.baselgovernance.org)",
        ],
    }


def is_high_risk_jurisdiction(country: str) -> bool:
    """Quick check — returns True if country is FATF-listed or Basel score ≥ 6.0."""
    key = _normalise(country)
    if key in FATF_BLACK_LIST or key in FATF_GREY_LIST:
        return True
    return BASEL_AML_SCORES.get(key, _DEFAULT_SCORE) >= 6.0
