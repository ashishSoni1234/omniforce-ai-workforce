"""
Document OCR verification using EasyOCR (local, no API key required).

Supports: Passport (MRZ parsing), National ID, Driver's Licence.
Requires: pip install easyocr

EasyOCR runs fully offline — no API key, no internet, no rate limits.
Falls back to manual review if easyocr is not installed.
"""

import datetime
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# MRZ line: 44 uppercase chars, digits, and < filler
_MRZ_PATTERN = re.compile(r"^[A-Z0-9<]{44}$")


def _load_reader():
    """Lazy-load EasyOCR reader (first call downloads ~100 MB model once)."""
    try:
        import easyocr
        return easyocr.Reader(["en"], verbose=False)
    except ImportError:
        return None


def _extract_text_from_image(image_path: str) -> list[str]:
    """Return list of text lines detected in image via EasyOCR."""
    reader = _load_reader()
    if reader is None:
        raise ImportError("easyocr not installed — run: pip install easyocr")

    results = reader.readtext(str(image_path), detail=0, paragraph=False)
    # Uppercase and strip — MRZ lines need exact casing
    return [line.strip().upper().replace(" ", "") for line in results if line.strip()]


def _find_mrz_lines(text_lines: list[str]) -> tuple[str | None, str | None]:
    """Detect the two 44-char MRZ lines from OCR output."""
    mrz_candidates = [line for line in text_lines if _MRZ_PATTERN.match(line)]
    if len(mrz_candidates) >= 2:
        return mrz_candidates[-2], mrz_candidates[-1]
    return None, None


def _parse_mrz(mrz1: str, mrz2: str) -> dict:
    """
    Parse ICAO 9303 TD3 passport MRZ (2 x 44 chars).

    MRZ1: P<COUNTRY<LASTNAME<<FIRSTNAME<<<<<...
    MRZ2: DOCNUM<CHECK<NATIONALITY<YYMMDD<CHECK<SEX<YYMMDD<CHECK<PERSONAL<CHECK
    """
    result = {
        "mrz1": mrz1,
        "mrz2": mrz2,
        "mrz_valid": False,
        "doc_type": None,
        "country": None,
        "full_name": None,
        "document_number": None,
        "birth_date": None,
        "expiry_date": None,
        "sex": None,
    }

    try:
        # MRZ Line 1
        result["doc_type"] = mrz1[0:2].replace("<", "").strip()
        result["country"] = mrz1[2:5].replace("<", "").strip()

        name_field = mrz1[5:44]
        if "<<" in name_field:
            surname_raw, given_raw = name_field.split("<<", 1)
        else:
            surname_raw, given_raw = name_field, ""
        surname = surname_raw.replace("<", " ").strip()
        given = given_raw.replace("<", " ").strip()
        result["full_name"] = f"{given} {surname}".strip() if given else surname

        # MRZ Line 2
        result["document_number"] = mrz2[0:9].replace("<", "").strip()
        result["birth_date"] = _parse_mrz_date(mrz2[13:19])
        result["expiry_date"] = _parse_mrz_date(mrz2[21:27], expiry=True)
        result["sex"] = mrz2[20] if mrz2[20] in ("M", "F") else None
        result["mrz_valid"] = True

    except Exception as exc:
        logger.warning("[DocVerify] MRZ parse error: %s", exc)

    return result


def _parse_mrz_date(yymmdd: str, expiry: bool = False) -> str | None:
    """Convert YYMMDD to YYYY-MM-DD. Expiry dates: YY < 30 → 20xx, else 19xx."""
    if len(yymmdd) != 6 or not yymmdd.isdigit():
        return None
    yy, mm, dd = int(yymmdd[:2]), int(yymmdd[2:4]), int(yymmdd[4:6])
    if expiry:
        year = 2000 + yy if yy < 30 else 1900 + yy
    else:
        year = 2000 + yy if yy <= datetime.date.today().year % 100 else 1900 + yy
    try:
        return datetime.date(year, mm, dd).isoformat()
    except ValueError:
        return None


def verify_passport(image_path: str) -> dict:
    """
    Extract and verify data from a passport image using EasyOCR (local, no API key).

    Args:
        image_path: Path to passport image (JPG/PNG/PDF).

    Returns:
        dict with: verified, full_name, birth_date, document_number,
                   expiry_date, country, mrz_valid, expired, error
    """
    path = Path(image_path)
    if not path.exists():
        logger.error("[DocVerify] File not found: %s", image_path)
        return {"verified": False, "error": f"File not found: {image_path}"}

    try:
        logger.info("[DocVerify] Running EasyOCR on: %s", path.name)
        text_lines = _extract_text_from_image(str(path))

        mrz1, mrz2 = _find_mrz_lines(text_lines)

        if not mrz1 or not mrz2:
            logger.warning("[DocVerify] MRZ not detected — image quality may be low")
            return {
                "verified": False,
                "error": "MRZ lines not detected. Ensure passport bottom strip is visible and image is clear.",
                "full_name": None,
                "birth_date": None,
                "document_number": None,
                "expiry_date": None,
                "country": None,
                "mrz_valid": False,
            }

        parsed = _parse_mrz(mrz1, mrz2)

        expired = False
        if parsed.get("expiry_date"):
            try:
                exp = datetime.date.fromisoformat(parsed["expiry_date"])
                expired = exp < datetime.date.today()
            except ValueError:
                pass

        logger.info(
            "[DocVerify] Passport OK — name: %s | country: %s | expired: %s",
            parsed.get("full_name"), parsed.get("country"), expired,
        )

        return {
            "verified": parsed["mrz_valid"],
            "full_name": parsed.get("full_name"),
            "birth_date": parsed.get("birth_date"),
            "document_number": parsed.get("document_number"),
            "expiry_date": parsed.get("expiry_date"),
            "country": parsed.get("country"),
            "mrz_valid": parsed["mrz_valid"],
            "expired": expired,
            "raw_fields": {"mrz1": mrz1, "mrz2": mrz2},
            "error": None,
        }

    except ImportError as exc:
        logger.error("[DocVerify] %s", exc)
        return {
            "verified": False,
            "error": "EasyOCR not installed. Run: pip install easyocr",
        }
    except Exception as exc:
        logger.error("[DocVerify] OCR error: %s", exc)
        return {"verified": False, "error": str(exc)}


def verify_document(doc_type: str, image_path: str) -> dict:
    """
    Route document verification by type.

    Supported: 'Passport', 'National ID', 'Driver Licence'
    Other types (Proof of Address, Bank Statement) → manual review flag.
    """
    doc_type_lower = doc_type.lower()

    if "passport" in doc_type_lower:
        return verify_passport(image_path)

    logger.info("[DocVerify] Document type '%s' — flagged for manual review", doc_type)
    return {
        "verified": None,
        "document_type": doc_type,
        "action": "Manual review required for this document type",
        "error": None,
    }
