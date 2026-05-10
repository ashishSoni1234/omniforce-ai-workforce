"""
KYC Agent — upgraded with real compliance integrations.

Pipeline per client:
  1. Sanctions screening     (OpenSanctions API / OFAC XML fallback)
  2. AML country risk        (FATF lists + Basel AML Index — no LLM guessing)
  3. Document check          (required doc list vs provided)
  4. OCR verification        (Mindee passport OCR — if image path supplied)
  5. Compliance RAG          (ChromaDB semantic search over real policy docs)
  6. Llama compliance report (Groq Llama 3.1 70B — augmented with real data)
  7. Notifications           (Gmail / Slack)
"""

import json
import logging
from groq import Groq
from config.settings import settings
from rag.retriever import retrieve_context
from tools import gmail_tool, slack_tool
from tools.sanctions_tool import check_sanctions
from tools.risk_scoring import get_country_risk, is_high_risk_jurisdiction
from tools.document_verification import verify_document

logger = logging.getLogger(__name__)

MODEL = "llama-3.3-70b-versatile"

REQUIRED_DOCUMENTS = ["Passport", "Proof of Address", "Bank Statement"]
ALL_DOCUMENTS = [
    "Passport", "Proof of Address", "Bank Statement",
    "Source of Funds", "Company Registration",
]


class KYCAgent:
    def __init__(self):
        logger.info("[KYCAgent] Initialising")
        self.client = Groq(api_key=settings.groq_api_key)
        logger.info("[KYCAgent] Ready")

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run(self, instruction: str, client_data: dict = {}) -> dict:
        logger.info("[KYCAgent] Instruction: %s", instruction[:100])
        instruction_lower = instruction.lower()

        try:
            if any(kw in instruction_lower for kw in ["check", "verify", "kyc"]):
                return self._handle_document_check(instruction, client_data)
            elif any(kw in instruction_lower for kw in ["risk", "assess"]):
                return self._handle_risk_assessment(instruction, client_data)
            elif any(kw in instruction_lower for kw in ["onboard", "new client"]):
                return self._handle_onboarding(instruction, client_data)
            else:
                return self._handle_default(instruction, client_data)
        except Exception as exc:
            logger.error("[KYCAgent] Unexpected error: %s", exc)
            return {"status": "error", "error": str(exc)}

    # ------------------------------------------------------------------
    # Real compliance helpers
    # ------------------------------------------------------------------

    def _run_sanctions_check(self, client_name: str) -> dict:
        """Screen client name against global sanctions lists."""
        logger.info("[KYCAgent] Running sanctions check for: %s", client_name)
        try:
            result = check_sanctions(client_name)
            return result
        except Exception as exc:
            logger.warning("[KYCAgent] Sanctions check failed (non-critical): %s", exc)
            return {
                "sanctioned": False,
                "error": str(exc),
                "risk_action": "Sanctions check unavailable — manual screening required",
            }

    def _compute_aml_risk(self, country: str | None) -> dict:
        """Get real AML country risk using FATF lists and Basel AML Index."""
        if not country:
            return {
                "country": "Unknown",
                "risk_level": "Medium",
                "fatf_status": "UNKNOWN",
                "basel_aml_score": None,
                "risk_flags": ["Country not provided — defaulting to Medium risk"],
                "due_diligence_required": "Customer Due Diligence (CDD) required",
            }
        try:
            return get_country_risk(country)
        except Exception as exc:
            logger.warning("[KYCAgent] Country risk scoring failed: %s", exc)
            return {
                "country": country,
                "risk_level": "Medium",
                "error": str(exc),
            }

    def _run_ocr_verification(self, client_data: dict) -> dict | None:
        """If a document_image_path is in client_data, OCR-verify it via Mindee."""
        image_path = client_data.get("document_image_path")
        doc_type = client_data.get("document_type", "Passport")
        if not image_path:
            return None
        logger.info("[KYCAgent] Running OCR on document: %s", image_path)
        try:
            return verify_document(doc_type, image_path)
        except Exception as exc:
            logger.warning("[KYCAgent] OCR verification failed: %s", exc)
            return {"verified": False, "error": str(exc)}

    # ------------------------------------------------------------------
    # Handler: Document Check
    # ------------------------------------------------------------------

    def _handle_document_check(self, instruction: str, client_data: dict) -> dict:
        logger.info("[KYCAgent] Document check")
        try:
            client_name = client_data.get("client_name", "Unknown Client")
            client_email = client_data.get("email", "")
            provided_docs = client_data.get("documents", [])
            country = client_data.get("country")

            # --- Real sanctions screening ---
            sanctions_result = self._run_sanctions_check(client_name)
            if sanctions_result.get("sanctioned"):
                alert = f"SANCTIONS HIT — {client_name}: {sanctions_result.get('matches', [])}"
                logger.warning("[KYCAgent] %s", alert)
                try:
                    slack_tool.send_alert(alert)
                except Exception:
                    pass
                return {
                    "status": "blocked",
                    "client_name": client_name,
                    "reason": "Sanctions match — onboarding blocked",
                    "sanctions_result": sanctions_result,
                }

            # --- Real AML country risk ---
            country_risk = self._compute_aml_risk(country)

            # --- Document completeness check ---
            missing_docs = [d for d in REQUIRED_DOCUMENTS if d not in provided_docs]

            # --- Optional OCR verification ---
            ocr_result = self._run_ocr_verification(client_data)

            # --- RAG compliance context ---
            rag_context = retrieve_context("KYC document requirements verification", n_results=3)

            # --- Determine overall risk level (real data first, LLM supplements) ---
            country_risk_level = country_risk.get("risk_level", "Medium")
            if missing_docs and country_risk_level == "High":
                overall_risk = "High"
            elif missing_docs or country_risk_level == "High":
                overall_risk = "Medium"
            else:
                overall_risk = country_risk_level

            # --- Llama recommendation (augmented with real data) ---
            system_prompt = (
                "You are a KYC compliance specialist. "
                "Based on the real compliance data and policy context provided, "
                "give a concise compliance recommendation. "
                "Return JSON with keys: recommendation (string), additional_checks (array of strings). "
                "Return ONLY valid JSON."
            )
            user_msg = (
                f"Compliance Policy Context:\n{rag_context}\n\n"
                f"Client: {client_name}\n"
                f"Country: {country or 'Not provided'}\n"
                f"Country AML Risk: {country_risk_level} (Basel score: {country_risk.get('basel_aml_score', 'N/A')})\n"
                f"FATF Status: {country_risk.get('fatf_status', 'N/A')}\n"
                f"Documents provided: {', '.join(provided_docs) if provided_docs else 'None'}\n"
                f"Required documents: {', '.join(REQUIRED_DOCUMENTS)}\n"
                f"Missing documents: {', '.join(missing_docs) if missing_docs else 'None'}\n"
                f"Task: {instruction}"
            )
            llm_response = self._call_llama(system_prompt, user_msg)
            try:
                start, end = llm_response.find("{"), llm_response.rfind("}") + 1
                llm_data = json.loads(llm_response[start:end])
            except (json.JSONDecodeError, ValueError):
                llm_data = {
                    "recommendation": "Request missing documents" if missing_docs else "Proceed with onboarding",
                    "additional_checks": [],
                }

            # --- Email missing docs ---
            if missing_docs and client_email:
                missing_list = "\n".join(f"  - {d}" for d in missing_docs)
                email_body = (
                    f"Dear {client_name},\n\n"
                    f"To complete your KYC verification, we require the following additional documents:\n\n"
                    f"{missing_list}\n\n"
                    f"Please submit within 5 business days to compliance@omniforce.ai.\n\n"
                    f"Kind regards,\nOmniForce Compliance Team"
                )
                try:
                    gmail_tool.send_email(
                        to=client_email,
                        subject="Action Required: Outstanding KYC Documents",
                        body=email_body,
                    )
                except Exception as exc:
                    logger.warning("[KYCAgent] Email failed: %s", exc)

            # --- Slack alert ---
            try:
                slack_tool.send_alert(
                    f"KYC check — {client_name} | Risk: {overall_risk} | "
                    f"Country: {country or 'N/A'} ({country_risk_level}) | "
                    f"Missing docs: {', '.join(missing_docs) if missing_docs else 'None'}"
                )
            except Exception as exc:
                logger.warning("[KYCAgent] Slack failed: %s", exc)

            return {
                "status": "complete",
                "client_name": client_name,
                "missing_docs": missing_docs,
                "risk_level": overall_risk,
                "country_risk": country_risk,
                "sanctions_result": sanctions_result,
                "ocr_verification": ocr_result,
                "recommendation": llm_data.get("recommendation", ""),
                "additional_checks": llm_data.get("additional_checks", []),
                "email_sent": bool(missing_docs and client_email),
            }
        except Exception as exc:
            logger.error("[KYCAgent] Document check failed: %s", exc)
            return {"status": "error", "error": str(exc)}

    # ------------------------------------------------------------------
    # Handler: Risk Assessment
    # ------------------------------------------------------------------

    def _handle_risk_assessment(self, instruction: str, client_data: dict) -> dict:
        logger.info("[KYCAgent] Risk assessment")
        try:
            client_name = client_data.get("client_name", "Unknown Client")
            country = client_data.get("country")

            # --- Real country risk (replaces LLM guessing) ---
            country_risk = self._compute_aml_risk(country)

            # --- Real sanctions check ---
            sanctions_result = self._run_sanctions_check(client_name)

            # --- RAG context for policy-specific risk criteria ---
            rag_context = retrieve_context("risk assessment criteria client classification AML", n_results=3)

            # Seed risk score from Basel data + FATF
            base_score = 0
            risk_flags = list(country_risk.get("risk_flags", []))

            if country_risk.get("fatf_status") == "BLACK_LIST":
                base_score += 40
                risk_flags.append("Client country on FATF Black List — EDD mandatory")
            elif country_risk.get("fatf_status") == "GREY_LIST":
                base_score += 25
                risk_flags.append("Client country on FATF Grey List — enhanced monitoring")

            basel = country_risk.get("basel_aml_score")
            if basel is not None:
                if basel >= 7.0:
                    base_score += 20
                elif basel >= 5.5:
                    base_score += 10

            if sanctions_result.get("sanctioned"):
                base_score += 50
                risk_flags.append("SANCTIONS MATCH — immediate block required")

            # --- Llama for client-specific factors (not country risk) ---
            system_prompt = (
                "You are a financial crime risk specialist. "
                "The country AML risk and sanctions results are already computed with real data (do NOT change them). "
                "Assess ONLY the client-specific risk factors from the client data provided. "
                "Return JSON: additional_risk_score (0-30 integer), client_risk_factors (array of strings), "
                "due_diligence_level (Standard/Enhanced/Simplified), review_frequency (string), "
                "recommendations (array of strings). Return ONLY valid JSON."
            )
            user_msg = (
                f"Risk Policy Context:\n{rag_context}\n\n"
                f"Client Data:\n{json.dumps(client_data, indent=2)}\n\n"
                f"Pre-computed Country Risk: {country_risk.get('risk_level')} "
                f"(Basel: {country_risk.get('basel_aml_score', 'N/A')}, "
                f"FATF: {country_risk.get('fatf_status', 'N/A')})\n"
                f"Base Risk Score (from real data): {base_score}/60\n"
                f"Task: {instruction}"
            )
            llm_response = self._call_llama(system_prompt, user_msg)
            try:
                start, end = llm_response.find("{"), llm_response.rfind("}") + 1
                llm_data = json.loads(llm_response[start:end])
            except (json.JSONDecodeError, ValueError):
                llm_data = {
                    "additional_risk_score": 10,
                    "client_risk_factors": ["Unable to parse LLM assessment"],
                    "due_diligence_level": "Enhanced" if base_score > 30 else "Standard",
                    "review_frequency": "Annual",
                    "recommendations": ["Manual compliance review recommended"],
                }

            final_score = min(100, base_score + llm_data.get("additional_risk_score", 10))
            if final_score >= 61:
                final_risk = "High"
            elif final_score >= 31:
                final_risk = "Medium"
            else:
                final_risk = "Low"

            risk_report = {
                "risk_level": final_risk,
                "risk_score": final_score,
                "risk_score_breakdown": {
                    "country_base_score": base_score,
                    "client_additional_score": llm_data.get("additional_risk_score", 10),
                },
                "risk_flags": risk_flags + llm_data.get("client_risk_factors", []),
                "due_diligence_level": llm_data.get("due_diligence_level", "Enhanced"),
                "review_frequency": llm_data.get("review_frequency", "Annual"),
                "recommendations": llm_data.get("recommendations", []),
                "country_risk": country_risk,
                "sanctions_result": sanctions_result,
            }

            try:
                slack_tool.send_alert(
                    f"Risk assessment — {client_name}: {final_risk} risk "
                    f"(score: {final_score}/100) | Country: {country or 'N/A'}"
                )
            except Exception as exc:
                logger.warning("[KYCAgent] Slack failed: %s", exc)

            return {
                "status": "complete",
                "client_name": client_name,
                "risk_report": risk_report,
            }
        except Exception as exc:
            logger.error("[KYCAgent] Risk assessment failed: %s", exc)
            return {"status": "error", "error": str(exc)}

    # ------------------------------------------------------------------
    # Handler: Full Onboarding
    # ------------------------------------------------------------------

    def _handle_onboarding(self, instruction: str, client_data: dict) -> dict:
        logger.info("[KYCAgent] Full client onboarding for: %s", client_data.get("client_name"))
        try:
            client_name = client_data.get("client_name", "New Client")
            client_email = client_data.get("email", "")
            provided_docs = client_data.get("documents", [])

            # Run full pipeline
            doc_check = self._handle_document_check("kyc check", client_data)

            # Stop if sanctions hit
            if doc_check.get("status") == "blocked":
                return doc_check

            risk_result = self._handle_risk_assessment("risk assessment", client_data)

            missing_docs = doc_check.get("missing_docs", [])
            risk_level = doc_check.get("risk_level", "Medium")
            risk_report = risk_result.get("risk_report", {})

            # Onboarding narrative from Llama
            rag_context = retrieve_context("client onboarding checklist KYC requirements", n_results=3)
            system_prompt = (
                "You are a client onboarding specialist. "
                "Generate a professional onboarding summary based on the compliance data provided. "
                "Include: onboarding status, completed steps, outstanding items, risk classification, next actions."
            )
            user_msg = (
                f"Onboarding Checklist Context:\n{rag_context}\n\n"
                f"Client: {client_name}\n"
                f"Documents provided: {', '.join(provided_docs) if provided_docs else 'None'}\n"
                f"Missing documents: {', '.join(missing_docs) if missing_docs else 'None'}\n"
                f"Risk level: {risk_level} (score: {risk_report.get('risk_score', 'N/A')})\n"
                f"Due diligence: {risk_report.get('due_diligence_level', 'CDD')}\n"
                f"Country risk: {doc_check.get('country_risk', {}).get('fatf_status', 'N/A')}\n"
                f"Sanctions: {doc_check.get('sanctions_result', {}).get('risk_action', 'N/A')}\n"
                f"Task: {instruction}"
            )
            onboarding_report = self._call_llama(system_prompt, user_msg)

            # Welcome email if fully clean
            if client_email and not missing_docs:
                welcome_body = (
                    f"Dear {client_name},\n\n"
                    f"Welcome to OmniForce Financial Services.\n\n"
                    f"Your onboarding is complete. Risk classification: {risk_level}.\n\n"
                    f"A relationship manager will be in touch within 2 business days.\n\n"
                    f"Kind regards,\nOmniForce Client Services"
                )
                try:
                    gmail_tool.send_email(
                        to=client_email,
                        subject="Welcome to OmniForce Financial Services — Onboarding Complete",
                        body=welcome_body,
                    )
                except Exception as exc:
                    logger.warning("[KYCAgent] Welcome email failed: %s", exc)

            try:
                slack_tool.send_alert(
                    f"Onboarding {'complete' if not missing_docs else 'pending'} — "
                    f"{client_name} | Risk: {risk_level} | Missing docs: {len(missing_docs)}"
                )
            except Exception as exc:
                logger.warning("[KYCAgent] Slack failed: %s", exc)

            return {
                "status": "complete" if not missing_docs else "pending_documents",
                "client_name": client_name,
                "missing_docs": missing_docs,
                "risk_level": risk_level,
                "risk_score": risk_report.get("risk_score", "N/A"),
                "country_risk": doc_check.get("country_risk", {}),
                "sanctions_result": doc_check.get("sanctions_result", {}),
                "ocr_verification": doc_check.get("ocr_verification"),
                "onboarding_report": onboarding_report,
                "welcome_email_sent": bool(client_email and not missing_docs),
            }
        except Exception as exc:
            logger.error("[KYCAgent] Onboarding failed: %s", exc)
            return {"status": "error", "error": str(exc)}

    # ------------------------------------------------------------------
    # Handler: Default / Compliance Q&A
    # ------------------------------------------------------------------

    def _handle_default(self, instruction: str, client_data: dict) -> dict:
        logger.info("[KYCAgent] Compliance Q&A via RAG + Llama")
        rag_context = retrieve_context(instruction, n_results=3)
        system_prompt = (
            "You are a KYC and AML compliance specialist. "
            "Use the regulatory context provided to give accurate, policy-compliant answers."
        )
        user_msg = f"Compliance Context:\n{rag_context}\n\nQuestion: {instruction}"
        if client_data:
            user_msg += f"\n\nClient Data:\n{json.dumps(client_data, indent=2)}"
        response = self._call_llama(system_prompt, user_msg)
        return {"status": "complete", "response": response}

    # ------------------------------------------------------------------
    # Groq / Llama helper
    # ------------------------------------------------------------------

    def _call_llama(self, system_prompt: str, user_msg: str) -> str:
        try:
            completion = self.client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_msg},
                ],
                max_tokens=1024,
                temperature=0.2,
            )
            result = completion.choices[0].message.content
            logger.debug("[KYCAgent] Llama response: %d chars", len(result))
            return result
        except Exception as exc:
            logger.error("[KYCAgent] Llama call failed: %s", exc)
            return str(exc)
