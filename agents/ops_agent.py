import json
from groq import Groq
from config.settings import settings
from tools import slack_tool, gmail_tool

MODEL = "llama-3.3-70b-versatile"


class OpsAgent:
    def __init__(self):
        print("[OpsAgent] Initializing")
        self.client = Groq(api_key=settings.groq_api_key)
        print("[OpsAgent] Groq client ready")

    def run(self, instruction: str, document_content: str = "") -> dict:
        print(f"[OpsAgent] Running instruction: {instruction[:100]}")
        instruction_lower = instruction.lower()

        try:
            if any(kw in instruction_lower for kw in ["invoice", "timesheet", "process"]):
                return self._handle_document_processing(instruction, document_content)
            elif any(kw in instruction_lower for kw in ["approve", "route", "review"]):
                return self._handle_approval_routing(instruction, document_content)
            elif any(kw in instruction_lower for kw in ["report", "summary"]):
                return self._handle_report_generation(instruction, document_content)
            else:
                return self._handle_default(instruction, document_content)
        except Exception as e:
            error_msg = f"[OpsAgent] Unexpected error: {str(e)}"
            print(error_msg)
            return {"status": "error", "error": error_msg}

    def _handle_document_processing(self, instruction: str, document_content: str) -> dict:
        print("[OpsAgent] Processing document")
        try:
            system_prompt = (
                "You are a financial document processing expert. "
                "Extract key fields from the document provided. "
                "Return a valid JSON object with these keys: "
                "type (string), amount (string with currency), date (string), "
                "vendor_or_employee (string), status (string: 'clean' or 'anomalous'), "
                "anomalies (array of strings describing unusual items, empty if none). "
                "Return ONLY valid JSON, no explanation."
            )
            doc_to_analyse = document_content if document_content.strip() else (
                f"Sample document for: {instruction}\n"
                "Invoice #1042 | Vendor: TechSupplies Ltd | Amount: £12,450.00 | Date: 2024-01-15 | "
                "Line items: Software licences x10 (£1,245 each) | Payment terms: 30 days"
            )

            response = self._call_llama(system_prompt, f"Document content:\n{doc_to_analyse}")

            try:
                start = response.find("{")
                end = response.rfind("}") + 1
                extracted = json.loads(response[start:end])
            except (json.JSONDecodeError, ValueError) as e:
                print(f"[OpsAgent] JSON parse warning: {e}")
                extracted = {
                    "type": "document",
                    "amount": "Unknown",
                    "date": "Unknown",
                    "vendor_or_employee": "Unknown",
                    "status": "clean",
                    "anomalies": [],
                    "raw_response": response,
                }

            anomalies = extracted.get("anomalies", [])
            has_anomalies = bool(anomalies)

            if has_anomalies:
                alert_msg = (
                    f"Document flagged with anomalies: {', '.join(anomalies)}. "
                    f"Vendor: {extracted.get('vendor_or_employee', 'Unknown')}, "
                    f"Amount: {extracted.get('amount', 'Unknown')}"
                )
                try:
                    slack_tool.send_alert(alert_msg)
                except Exception as e:
                    print(f"[OpsAgent] Slack alert failed (non-critical): {e}")
            else:
                alert_msg = (
                    f"Document processing complete. Status: clean. "
                    f"Vendor: {extracted.get('vendor_or_employee', 'Unknown')}, "
                    f"Amount: {extracted.get('amount', 'Unknown')}"
                )
                try:
                    slack_tool.send_alert(alert_msg)
                except Exception as e:
                    print(f"[OpsAgent] Slack alert failed (non-critical): {e}")

            print(f"[OpsAgent] Document processed. Anomalies: {len(anomalies)}")
            return {
                "status": "complete",
                "extracted_data": extracted,
                "has_anomalies": has_anomalies,
                "anomaly_report": anomalies if has_anomalies else "No anomalies detected",
            }
        except Exception as e:
            error_msg = f"[OpsAgent] Document processing failed: {str(e)}"
            print(error_msg)
            return {"status": "error", "error": error_msg}

    def _handle_approval_routing(self, instruction: str, document_content: str) -> dict:
        print("[OpsAgent] Handling approval routing")
        try:
            system_prompt = (
                "You are a financial operations approval specialist. "
                "Analyse the document or instruction and determine the approval level required. "
                "Apply these thresholds: Low = under £1,000, Medium = £1,000-£10,000, High = over £10,000. "
                "Return a JSON object with: amount (string), approval_level (Low/Medium/High), "
                "approver (string: Team Lead / Finance Manager / CFO), reason (string). "
                "Return ONLY valid JSON."
            )
            content = document_content if document_content.strip() else instruction
            response = self._call_llama(system_prompt, f"Routing request:\n{content}")

            try:
                start = response.find("{")
                end = response.rfind("}") + 1
                routing = json.loads(response[start:end])
            except (json.JSONDecodeError, ValueError) as e:
                print(f"[OpsAgent] JSON parse warning: {e}")
                routing = {
                    "amount": "Unknown",
                    "approval_level": "Medium",
                    "approver": "Finance Manager",
                    "reason": response,
                }

            alert_msg = (
                f"Approval routing decision: {routing.get('approval_level', 'Unknown')} level required. "
                f"Amount: {routing.get('amount', 'Unknown')}. "
                f"Assigned to: {routing.get('approver', 'Finance Manager')}"
            )
            try:
                slack_tool.send_alert(alert_msg)
            except Exception as e:
                print(f"[OpsAgent] Slack alert failed (non-critical): {e}")

            print(f"[OpsAgent] Routing complete: {routing.get('approval_level')} — {routing.get('approver')}")
            return {"status": "complete", "routing_decision": routing}
        except Exception as e:
            error_msg = f"[OpsAgent] Approval routing failed: {str(e)}"
            print(error_msg)
            return {"status": "error", "error": error_msg}

    def _handle_report_generation(self, instruction: str, document_content: str) -> dict:
        print("[OpsAgent] Generating ops report")
        try:
            system_prompt = (
                "You are a financial operations reporting specialist. "
                "Generate a concise, professional operational report based on the input provided. "
                "Structure the report with: Executive Summary, Key Metrics, Issues Identified, "
                "Recommended Actions, and Next Steps. Use clear, formal language."
            )
            content = document_content if document_content.strip() else instruction
            report_content = self._call_llama(system_prompt, f"Generate report for:\n{content}")

            report_data = {
                "Report Title": f"OmniForce Ops Report — {instruction[:50]}",
                "Generated": "Auto-generated by OmniForce AI Workforce",
                "Content": report_content[:500] + ("..." if len(report_content) > 500 else ""),
            }

            try:
                slack_tool.send_ops_report(report_data)
            except Exception as e:
                print(f"[OpsAgent] Slack report send failed (non-critical): {e}")

            print("[OpsAgent] Report generated successfully")
            return {"status": "complete", "report": report_content}
        except Exception as e:
            error_msg = f"[OpsAgent] Report generation failed: {str(e)}"
            print(error_msg)
            return {"status": "error", "error": error_msg}

    def _handle_default(self, instruction: str, document_content: str) -> dict:
        print("[OpsAgent] Handling default instruction via Llama")
        system_prompt = (
            "You are an expert financial operations manager specialising in document processing, "
            "workflow automation, compliance, and approval routing for financial services firms. "
            "Provide concise, actionable, professional responses."
        )
        content = f"{instruction}\n\nDocument:\n{document_content}" if document_content.strip() else instruction
        response = self._call_llama(system_prompt, content)
        return {"status": "complete", "response": response}

    def _call_llama(self, system_prompt: str, user_msg: str) -> str:
        print(f"[OpsAgent] Calling Llama | system={system_prompt[:60]}...")
        try:
            completion = self.client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_msg},
                ],
                max_tokens=1024,
                temperature=0.3,
            )
            result = completion.choices[0].message.content
            print(f"[OpsAgent] Llama response received ({len(result)} chars)")
            return result
        except Exception as e:
            error_msg = f"[OpsAgent] Llama call failed: {str(e)}"
            print(error_msg)
            return error_msg
