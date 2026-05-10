import os
import streamlit as st
import requests
import json

API_BASE = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")

st.set_page_config(
    page_title="OmniForce AI Workforce",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🤖 OmniForce AI Workforce")
st.caption("Autonomous AI agents for financial services — powered by Llama 3.1 70B")

with st.sidebar:
    st.header("⚡ Agent Control Panel")
    agent_choice = st.radio(
        "Select Agent",
        ["Sales Agent", "Ops Agent", "KYC Agent"],
        index=0,
    )

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
    st.caption("LLM: Llama 3.1 70B via Groq")
    st.caption("RAG: ChromaDB + MiniLM-L6-v2")


def post_to_api(payload: dict) -> dict | None:
    try:
        response = requests.post(f"{API_BASE}/run", json=payload, timeout=120)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.ConnectionError:
        st.error(f"Cannot connect to OmniForce API at {API_BASE}. Check BACKEND_URL environment variable.")
        return None
    except requests.exceptions.Timeout:
        st.error("Request timed out. The agent may still be processing — check the backend logs.")
        return None
    except requests.exceptions.HTTPError as e:
        st.error(f"API error {e.response.status_code}: {e.response.text}")
        return None
    except Exception as e:
        st.error(f"Unexpected error: {str(e)}")
        return None


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
        color = "green" if status == "complete" else "orange" if status == "pending_documents" else "red"
        st.metric("Status", status)

    if error:
        st.error(f"Error: {error}")
        return

    if agent_result:
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
                payload = {
                    "agent": "sales",
                    "instruction": instruction,
                    "context": {},
                }
                result = post_to_api(payload)
                render_result(result)

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
                    render_result({"success": resp_json.get("success"), "result": {"agent_used": "ops", "status": resp_json.get("result", {}).get("status"), "result": resp_json.get("result", {})}})
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
                render_result(result)

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
                payload = {
                    "agent": "kyc",
                    "instruction": instruction,
                    "context": {"client_data": client_data},
                }
                result = post_to_api(payload)
                render_result(result)

st.divider()
st.subheader("📊 Current Leads in CRM")

if st.button("🔄 Fetch Leads from CRM", key="fetch_leads"):
    with st.spinner("Fetching leads from Airtable..."):
        try:
            response = requests.get(f"{API_BASE}/leads", timeout=15)
            response.raise_for_status()
            data = response.json()
            leads = data.get("leads", [])

            if leads:
                st.success(f"Found {len(leads)} leads in CRM")
                display_leads = []
                for lead in leads:
                    display_leads.append(
                        {
                            "Company": lead.get("Company Name", lead.get("company_name", "N/A")),
                            "Industry": lead.get("Industry", lead.get("industry", "N/A")),
                            "Revenue": lead.get("Revenue Range", lead.get("revenue_range", "N/A")),
                            "Location": lead.get("Location", lead.get("location", "N/A")),
                            "Status": lead.get("Status", lead.get("status", "N/A")),
                            "Email": lead.get("Contact Email", lead.get("contact_email", "")),
                        }
                    )
                st.dataframe(display_leads, use_container_width=True)
            else:
                st.info("No leads found in CRM. Run the Sales Agent to add leads.")

        except requests.exceptions.ConnectionError:
            st.error("Cannot connect to API. Ensure the backend is running.")
        except requests.exceptions.HTTPError as e:
            st.error(f"API error: {e.response.status_code} — {e.response.text}")
        except Exception as e:
            st.error(f"Failed to fetch leads: {str(e)}")

st.divider()
st.caption("OmniForce AI Workforce v1.0.0 | Built with LangGraph + Groq + ChromaDB")
