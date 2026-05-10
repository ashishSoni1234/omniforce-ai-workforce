import json
from groq import Groq
from config.settings import settings
from tools import airtable_tool, web_search_tool, gmail_tool, slack_tool

MODEL = "llama-3.3-70b-versatile"


class SalesAgent:
    def __init__(self):
        print("[SalesAgent] Initializing")
        self.client = Groq(api_key=settings.groq_api_key)
        print("[SalesAgent] Groq client ready")

    def run(self, instruction: str) -> dict:
        print(f"[SalesAgent] Running instruction: {instruction[:100]}")
        instruction_lower = instruction.lower()

        try:
            if any(kw in instruction_lower for kw in ["find", "research", "prospect"]):
                return self._handle_lead_research(instruction)
            elif any(kw in instruction_lower for kw in ["follow", "email", "chase"]):
                return self._handle_followup_email(instruction)
            elif any(kw in instruction_lower for kw in ["update", "crm", "status"]):
                return self._handle_crm_update(instruction)
            else:
                return self._handle_default(instruction)
        except Exception as e:
            error_msg = f"[SalesAgent] Unexpected error: {str(e)}"
            print(error_msg)
            return {"status": "error", "error": error_msg}

    def _handle_lead_research(self, instruction: str) -> dict:
        print("[SalesAgent] Handling lead research")
        try:
            # Extract count from instruction
            count = 5
            try:
                count_raw = self._call_llama(
                    "You are a number extraction assistant. Return only a single integer, nothing else.",
                    f"How many companies is the user asking for? Return ONLY the number.\nInstruction: {instruction}"
                ).strip()
                digits = "".join(filter(str.isdigit, count_raw))
                count = min(max(int(digits), 1), 15) if digits else 5
            except Exception:
                count = 5
            print(f"[SalesAgent] Requested count: {count}")

            # Best prompt — LLM generates all data directly
            system_prompt = (
                "You are an elite B2B sales intelligence analyst with deep knowledge of global startups, "
                "technology companies, and business data up to 2025.\n\n"
                "STRICT RULES:\n"
                "- Return ONLY a valid JSON array. No markdown, no explanation, no text before or after.\n"
                "- Every field must be factual and based on real companies.\n"
                "- company_type must be SPECIFIC (e.g. 'Fantasy Sports Platform', 'B2B SaaS', "
                "'Quick Commerce', 'AI Infrastructure', 'FinTech Lending'). NEVER just 'Technology'.\n"
                "- revenue_range must be ACTUAL ANNUAL REVENUE (ARR), NOT funding raised or valuation. "
                "Example: '$500M ARR', '$1B+ ARR', '$10M-$50M ARR', 'Not publicly disclosed'.\n"
                "- contact_email must be suitable for B2B sales outreach. "
                "Use: partnerships@, business@, sales@, hello@, info@ — NEVER support@, noreply@, admin@.\n"
                "- If email is genuinely unknown, construct it as info@{domain} from the website URL.\n"
                "- founded_year must be a 4-digit year as a string.\n"
                "- funding_stage must be one of: Pre-Seed, Seed, Series A, Series B, Series C, "
                "Series D+, Growth Stage, Public, Bootstrapped.\n"
                "- website_url must be the real official homepage URL.\n"
                "- linkedin_url format: https://www.linkedin.com/company/{company-slug}"
            )

            user_prompt = (
                f"Find the top {count} companies/startups matching this query: \"{instruction}\"\n\n"
                f"Return a JSON array with exactly {count} objects:\n"
                f"[\n"
                f"  {{\n"
                f"    \"company_name\": \"Exact official company name\",\n"
                f"    \"company_type\": \"Specific industry sector — be very precise\",\n"
                f"    \"revenue_range\": \"Annual revenue/ARR only, not valuation\",\n"
                f"    \"location\": \"City, Country\",\n"
                f"    \"contact_email\": \"Best B2B outreach email\",\n"
                f"    \"founded_year\": \"YYYY\",\n"
                f"    \"founders\": \"Founder Name 1, Founder Name 2\",\n"
                f"    \"funding_stage\": \"Current stage\",\n"
                f"    \"website_url\": \"https://www.company.com\",\n"
                f"    \"linkedin_url\": \"https://www.linkedin.com/company/company-name\"\n"
                f"  }}\n"
                f"]\n\n"
                f"Return ONLY the JSON array. No explanation. No markdown code blocks."
            )

            raw = self._call_llama(system_prompt, user_prompt)
            print(f"[SalesAgent] LLM raw response: {raw[:300]}")

            # Parse JSON
            companies = []
            try:
                start = raw.find("[")
                end = raw.rfind("]") + 1
                if start != -1 and end > start:
                    companies = json.loads(raw[start:end])
                    print(f"[SalesAgent] Parsed {len(companies)} companies from LLM")
                else:
                    raise ValueError("No JSON array found in response")
            except Exception as e:
                print(f"[SalesAgent] JSON parse failed: {e}")
                return {"status": "error", "error": f"LLM returned invalid JSON: {str(e)}"}

            leads_added = 0
            lead_summaries = []

            for item in companies[:count]:
                if not isinstance(item, dict):
                    continue
                company_name = item.get("company_name", "").strip()
                if not company_name:
                    continue

                lead = {
                    "company_name": company_name,
                    "industry": item.get("company_type", ""),
                    "revenue_range": item.get("revenue_range", ""),
                    "location": item.get("location", ""),
                    "contact_email": item.get("contact_email", ""),
                    "founded_year": item.get("founded_year", ""),
                    "founders": item.get("founders", ""),
                    "funding_stage": item.get("funding_stage", ""),
                    "website_url": item.get("website_url", ""),
                    "linkedin_url": item.get("linkedin_url", ""),
                    "status": "new",
                }
                try:
                    airtable_tool.add_lead(lead)
                    leads_added += 1
                    lead_summaries.append(
                        f"- {company_name} | {item.get('company_type', '')} | "
                        f"{item.get('location', '')} | {item.get('revenue_range', '')}"
                    )
                    print(f"[SalesAgent] Lead added: {company_name}")
                except Exception as e:
                    print(f"[SalesAgent] Could not add lead {company_name}: {e}")

            llm_summary = self._call_llama(
                "You are a sales intelligence assistant. Write a concise professional summary.",
                f"Summarise these {leads_added} leads added to CRM for query: '{instruction}'.\n"
                + "\n".join(lead_summaries),
            )

            try:
                slack_tool.send_alert(f"Sales Agent: Added {leads_added} leads for: '{instruction[:60]}'")
            except Exception as e:
                print(f"[SalesAgent] Slack alert failed (non-critical): {e}")

            return {
                "status": "complete",
                "leads_added": leads_added,
                "companies": lead_summaries,
                "summary": llm_summary,
            }
        except Exception as e:
            error_msg = f"[SalesAgent] Lead research failed: {str(e)}"
            print(error_msg)
            return {"status": "error", "error": error_msg}

    def _handle_followup_email(self, instruction: str) -> dict:
        print("[SalesAgent] Handling follow-up email")
        try:
            extract_prompt = (
                f"Extract the company name from this instruction. "
                f"Return ONLY the company name, nothing else.\nInstruction: {instruction}"
            )
            company_name = self._call_llama(
                "You are a data extraction assistant. Extract only the requested field.",
                extract_prompt,
            ).strip().strip('"').strip("'")

            print(f"[SalesAgent] Extracted company name: {company_name}")

            leads = []
            try:
                leads = airtable_tool.search_leads(company_name)
            except Exception as e:
                print(f"[SalesAgent] Could not search CRM: {e}")

            contact_name = "Valued Client"
            contact_email = None
            if leads:
                lead = leads[0]
                contact_email = lead.get("Contact Email") or lead.get("contact_email")
                contact_name = lead.get("Company Name", company_name)

            email_content = gmail_tool.draft_followup_email(company_name, contact_name)

            email_sent = False
            if contact_email:
                try:
                    gmail_tool.send_email(
                        to=contact_email,
                        subject=f"Following Up — Partnership Opportunity with OmniForce AI",
                        body=email_content,
                    )
                    email_sent = True
                    print(f"[SalesAgent] Email sent to {contact_email}")
                except Exception as e:
                    print(f"[SalesAgent] Email send failed: {e}")
            else:
                print("[SalesAgent] No contact email found — email drafted but not sent")

            return {
                "status": "sent" if email_sent else "drafted",
                "company": company_name,
                "contact_email": contact_email or "Not found in CRM",
                "email_drafted": email_content,
                "email_sent": email_sent,
            }
        except Exception as e:
            error_msg = f"[SalesAgent] Follow-up email failed: {str(e)}"
            print(error_msg)
            return {"status": "error", "error": error_msg}

    def _handle_crm_update(self, instruction: str) -> dict:
        print("[SalesAgent] Handling CRM update")
        try:
            extract_prompt = (
                f"Extract the company name and new status from this CRM update instruction. "
                f"Return as JSON with keys 'company' and 'status'. "
                f"Valid statuses: new, Contacted, Replied, Closed\n"
                f"Instruction: {instruction}"
            )
            response = self._call_llama(
                "You are a CRM data extraction assistant. Return valid JSON only.",
                extract_prompt,
            )

            try:
                start = response.find("{")
                end = response.rfind("}") + 1
                parsed = json.loads(response[start:end])
                company = parsed.get("company", "")
                new_status = parsed.get("status", "Contacted")
            except (json.JSONDecodeError, ValueError) as e:
                print(f"[SalesAgent] JSON parse error: {e} — using defaults")
                company = instruction
                new_status = "Contacted"  # valid Airtable choice

            leads = []
            try:
                leads = airtable_tool.search_leads(company)
            except Exception as e:
                print(f"[SalesAgent] CRM search failed: {e}")

            updated_count = 0
            for lead in leads:
                record_id = lead.get("id")
                if record_id:
                    try:
                        airtable_tool.update_lead_status(record_id, new_status)
                        updated_count += 1
                    except Exception as e:
                        print(f"[SalesAgent] Failed to update record {record_id}: {e}")

            print(f"[SalesAgent] Updated {updated_count} records for '{company}' to '{new_status}'")
            return {
                "status": "updated",
                "company": company,
                "new_status": new_status,
                "records_updated": updated_count,
            }
        except Exception as e:
            error_msg = f"[SalesAgent] CRM update failed: {str(e)}"
            print(error_msg)
            return {"status": "error", "error": error_msg}

    def _handle_default(self, instruction: str) -> dict:
        print("[SalesAgent] Handling default instruction via Llama")
        system_prompt = (
            "You are an expert B2B sales agent specialising in financial services. "
            "You help with lead generation, prospect research, CRM management, "
            "follow-up strategies, and sales pipeline optimisation. "
            "Provide concise, actionable, professional responses."
        )
        response = self._call_llama(system_prompt, instruction)
        return {"status": "complete", "response": response}

    def _call_llama(self, system_prompt: str, user_msg: str) -> str:
        print(f"[SalesAgent] Calling Llama | system={system_prompt[:60]}...")
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
            print(f"[SalesAgent] Llama response received ({len(result)} chars)")
            return result
        except Exception as e:
            error_msg = f"[SalesAgent] Llama call failed: {str(e)}"
            print(error_msg)
            return error_msg
