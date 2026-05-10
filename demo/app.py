import os
import streamlit as st
import requests

API_BASE = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")

st.set_page_config(
    page_title="OmniForce AI Workforce",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Session state initialisation ──────────────────────────────────────────────
for key in ("sales_result", "ops_result", "kyc_result", "leads", "_last_agent"):
    if key not in st.session_state:
        st.session_state[key] = None

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚡ Agent Control Panel")
    agent_choice = st.radio(
        "Select Agent",
        ["Sales Agent", "Ops Agent", "KYC Agent"],
        index=0,
    )

    # Clear stale result when user switches agents
    _agent_key_map = {"Sales Agent": "sales_result", "Ops Agent": "ops_result", "KYC Agent": "kyc_result"}
    if st.session_state._last_agent != agent_choice:
        # Clear the result of the PREVIOUSLY selected agent so it doesn't bleed into new tab
        if st.session_state._last_agent and st.session_state._last_agent in _agent_key_map:
            pass  # keep previous results — just don't show wrong agent's result
        st.session_state._last_agent = agent_choice
    st.divider()
    if agent_choice == "Sales Agent":
        st.info(
            "**Sales Agent**\n\n"
            "Automates lead research, CRM management, and follow-up communications. "
            "Searches for prospects, adds them to Airtable, and drafts personalised outreach."
        )
    elif agent_choice == "Ops Agent":
        st.info(
            "**Ops Agent**\n\n"
            "Processes financial documents (invoices, timesheets), detects anomalies, "
            "routes approvals by value tier, and generates operational reports."
        )
    else:
        st.info(
            "**KYC Agent**\n\n"
            "Handles Know Your Customer compliance: verifies documents against regulatory "
            "requirements, assesses client risk, and manages onboarding workflows."
        )
    st.divider()
    st.caption("Backend: FastAPI + LangGraph")
    st.caption("LLM: Llama 3.3 70B via Groq")
    st.caption("RAG: ChromaDB + MiniLM-L6-v2")

st.title("🤖 OmniForce AI Workforce")
st.caption("Autonomous AI agents for financial services — powered by Llama 3.3 70B")


# ── API helpers ───────────────────────────────────────────────────────────────

def post_to_api(payload: dict) -> dict | None:
    try:
        response = requests.post(f"{API_BASE}/run", json=payload, timeout=120)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.ConnectionError:
        st.error(f"Cannot connect to OmniForce API at {API_BASE}. Check BACKEND_URL environment variable.")
        return None
    except requests.exceptions.Timeout:
        st.error("Request timed out (120s). The agent may still be processing — check the backend logs.")
        return None
    except requests.exceptions.HTTPError as e:
        st.error(f"API error {e.response.status_code}: {e.response.text}")
        return None
    except Exception as e:
        st.error(f"Unexpected error: {str(e)}")
        return None


# ── Result renderer ───────────────────────────────────────────────────────────

def render_result(result_data: dict):
    if result_data is None:
        return

    success = result_data.get("success", False)
    result = result_data.get("result", {})

    if not success:
        st.error(f"Agent returned an error: {result_data.get('error', 'Unknown error')}")
        return

    agent_used = result.get("agent_used", "unknown")
    status = result.get("status", "unknown")
    agent_result = result.get("result", {})
    error = result.get("error")

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Agent Used", agent_used.upper())
    with col2:
        st.metric("Status", status)

    if error:
        st.error(f"Error: {error}")
        return

    if not agent_result:
        return

    with st.expander("Full Result (JSON)", expanded=True):
        st.json(agent_result)

    if "summary" in agent_result:
        st.subheader("Summary")
        st.write(agent_result["summary"])

    if "response" in agent_result:
        st.subheader("Agent Response")
        st.write(agent_result["response"])

    if "report" in agent_result:
        st.subheader("Generated Report")
        st.write(agent_result["report"])

    if "email_drafted" in agent_result:
        st.subheader("Drafted Email")
        st.code(agent_result["email_drafted"], language="text")

    if "leads_added" in agent_result:
        st.success(f"✅ {agent_result['leads_added']} leads added to CRM")
        if "companies" in agent_result:
            st.write("Companies found:")
            for company in agent_result["companies"]:
                st.write(company)

    if "risk_level" in agent_result:
        risk = agent_result["risk_level"]
        if risk == "Low":
            st.success(f"✅ Risk Level: {risk}")
        elif risk == "Medium":
            st.warning(f"⚠️ Risk Level: {risk}")
        else:
            st.error(f"🚨 Risk Level: {risk}")

    if "missing_docs" in agent_result:
        missing = agent_result.get("missing_docs", [])
        if missing:
            st.warning(f"Missing Documents: {', '.join(missing)}")
        else:
            st.success("All required documents provided")

    if "routing_decision" in agent_result:
        routing = agent_result["routing_decision"]
        st.subheader("Approval Routing Decision")
        level = routing.get("approval_level", "Unknown")
        if level == "Low":
            st.success(f"✅ {level} — {routing.get('approver', '')}")
        elif level == "Medium":
            st.warning(f"⚠️ {level} — {routing.get('approver', '')}")
        else:
            st.error(f"🚨 {level} — {routing.get('approver', '')}")
        if routing.get("reason"):
            st.write(f"Reason: {routing['reason']}")


# ── Sales Agent tab ───────────────────────────────────────────────────────────

if agent_choice == "Sales Agent":
    st.header("🎯 Sales Agent")

    instruction = st.text_area(
        "Give instruction to Sales Agent",
        placeholder="Find 10 fintech companies in London doing £5-20M revenue",
        height=100,
        key="sales_instruction",
    )

    if st.button("🚀 Run Sales Agent", type="primary", key="sales_run"):
        if not instruction.strip():
            st.warning("Please enter an instruction before running the agent.")
        else:
            with st.spinner("Sales Agent working..."):
                payload = {"agent": "sales", "instruction": instruction, "context": {}}
                result = post_to_api(payload)
                if result:
                    st.session_state.sales_result = result

    if st.session_state.sales_result:
        st.divider()
        st.subheader("Last Result")
        render_result(st.session_state.sales_result)


# ── Ops Agent tab ─────────────────────────────────────────────────────────────

elif agent_choice == "Ops Agent":
    st.header("⚙️ Ops Agent")

    instruction = st.text_area(
        "Instruction",
        placeholder="Process this invoice and check for anomalies",
        height=100,
        key="ops_instruction",
    )

    input_mode = st.radio("Input method", ["Upload PDF", "Paste text"], horizontal=True, key="ops_mode")

    uploaded_pdf = None
    document_content = ""

    if input_mode == "Upload PDF":
        uploaded_pdf = st.file_uploader("Upload invoice PDF", type=["pdf"], key="ops_pdf")
        if uploaded_pdf:
            st.success(f"File ready: {uploaded_pdf.name}")
    else:
        document_content = st.text_area(
            "Paste document content here (leave blank for demo data)",
            placeholder="Invoice #1042 | Vendor: TechSupplies Ltd | Amount: £12,450.00 | ...",
            height=150,
            key="ops_document",
        )

    if st.button("🚀 Run Ops Agent", type="primary", key="ops_run"):
        if not instruction.strip():
            st.warning("Please enter an instruction before running the agent.")
        elif input_mode == "Upload PDF" and uploaded_pdf:
            with st.spinner("Ops Agent processing PDF..."):
                try:
                    files = {"file": (uploaded_pdf.name, uploaded_pdf.getvalue(), "application/pdf")}
                    data = {"instruction": instruction}
                    response = requests.post(f"{API_BASE}/upload-invoice", files=files, data=data, timeout=60)
                    response.raise_for_status()
                    resp_json = response.json()
                    result = {
                        "success": resp_json.get("success"),
                        "result": {
                            "agent_used": "ops",
                            "status": resp_json.get("result", {}).get("status"),
                            "result": resp_json.get("result", {}),
                        },
                    }
                    st.session_state.ops_result = result
                except requests.exceptions.ConnectionError:
                    st.error("Cannot connect to OmniForce API. Make sure the backend is running.")
                except Exception as e:
                    st.error(f"Upload failed: {str(e)}")
        else:
            with st.spinner("Ops Agent processing document..."):
                payload = {
                    "agent": "ops",
                    "instruction": instruction,
                    "context": {"document": document_content},
                }
                result = post_to_api(payload)
                if result:
                    st.session_state.ops_result = result

    if st.session_state.ops_result:
        st.divider()
        st.subheader("Last Result")
        render_result(st.session_state.ops_result)


# ── KYC Agent tab ─────────────────────────────────────────────────────────────

else:
    st.header("🔍 KYC Agent")

    instruction = st.text_area(
        "Instruction",
        placeholder="Run KYC check for new client",
        height=80,
        key="kyc_instruction",
    )

    col1, col2 = st.columns(2)
    with col1:
        client_name = st.text_input("Client Name", placeholder="Jane Smith", key="kyc_name")
    with col2:
        client_email = st.text_input("Client Email", placeholder="jane.smith@company.com", key="kyc_email")

    documents_provided = st.multiselect(
        "Documents Provided",
        options=["Passport", "Proof of Address", "Bank Statement", "Source of Funds", "Company Registration"],
        default=[],
        key="kyc_docs",
    )

    if st.button("🚀 Run KYC Check", type="primary", key="kyc_run"):
        if not instruction.strip():
            st.warning("Please enter an instruction before running the agent.")
        else:
            with st.spinner("KYC Agent verifying compliance..."):
                client_data = {
                    "client_name": client_name or "Unknown Client",
                    "email": client_email,
                    "documents": documents_provided,
                }
                payload = {"agent": "kyc", "instruction": instruction, "context": {"client_data": client_data}}
                result = post_to_api(payload)
                if result:
                    st.session_state.kyc_result = result

    if st.session_state.kyc_result:
        st.divider()
        st.subheader("Last Result")
        render_result(st.session_state.kyc_result)


# ── Leads / CRM section ───────────────────────────────────────────────────────

st.divider()
st.subheader("📊 Current Leads in CRM")

col_btn, col_clear = st.columns([1, 5])
with col_btn:
    fetch_clicked = st.button("🔄 Fetch Leads", key="fetch_leads")
with col_clear:
    if st.button("🗑️ Clear", key="clear_leads"):
        st.session_state.leads = None

if fetch_clicked:
    with st.spinner("Fetching leads from Airtable..."):
        try:
            response = requests.get(f"{API_BASE}/leads", timeout=15)
            response.raise_for_status()
            data = response.json()
            st.session_state.leads = data.get("leads", [])
        except requests.exceptions.ConnectionError:
            st.error("Cannot connect to API. Ensure the backend is running.")
        except requests.exceptions.HTTPError as e:
            st.error(f"API error: {e.response.status_code} — {e.response.text}")
        except Exception as e:
            st.error(f"Failed to fetch leads: {str(e)}")

if st.session_state.leads is not None:
    leads = st.session_state.leads
    if not leads:
        st.info("No leads found in CRM. Run the Sales Agent to add leads.")
    else:
        st.success(f"Found {len(leads)} leads in CRM — sorted oldest → newest (latest at bottom)")
        display_leads = []
        for i, lead in enumerate(leads, start=1):
            created_raw = lead.get("_created", "")
            # Format: 2024-01-15T10:30:00.000Z → 2024-01-15 10:30
            created_fmt = created_raw[:16].replace("T", " ") if created_raw else ""
            display_leads.append({
                "#": i,
                "Company": lead.get("Company Name") or lead.get("company_name") or "N/A",
                "Industry": lead.get("Industry") or lead.get("industry") or "N/A",
                "Revenue": lead.get("Revenue Range") or lead.get("revenue_range") or "N/A",
                "Location": lead.get("Location") or lead.get("location") or "N/A",
                "Status": lead.get("Status") or lead.get("status") or "N/A",
                "Email": lead.get("Contact Email") or lead.get("contact_email") or "",
                "Founded": lead.get("Founded Year") or lead.get("founded_year") or "",
                "Founders": lead.get("Founders") or lead.get("founders") or "",
                "Stage": lead.get("Funding Stage\t") or lead.get("Funding Stage") or lead.get("funding_stage") or "",
                "Website": lead.get("Website URL") or lead.get("website_url") or "",
                "LinkedIn": lead.get("LinkedIn URL") or lead.get("linkedin_url") or "",
                "Created At": created_fmt,
            })
        st.dataframe(display_leads, use_container_width=True)
        st.caption("📌 Leads are sorted by creation time — latest leads appear at the bottom")

st.divider()
st.caption("OmniForce AI Workforce v1.0.0 | Built with LangGraph + Groq + ChromaDB")
