from pyairtable import Api
from config.settings import settings


def _get_table():
    api = Api(settings.airtable_api_key)
    return api.table(settings.airtable_base_id, settings.airtable_table_name)


def add_lead(lead: dict) -> dict:
    print(f"[Airtable] Adding lead: {lead.get('company_name', 'Unknown')}")
    try:
        table = _get_table()
        # Core fields (always present in Airtable)
        fields = {
            "Company Name": lead.get("company_name", ""),
            "Industry": lead.get("industry", ""),
            "Revenue Range": lead.get("revenue_range", ""),
            "Location": lead.get("location", ""),
            "Contact Email": lead.get("contact_email", ""),
            "Status": lead.get("status", "new"),
        }
        # Optional extended fields — only add if value exists
        # NOTE: Airtable field "Funding Stage" has a trailing tab in its name
        extended = {
            "Founded Year": str(lead.get("founded_year", "")),
            "Founders": lead.get("founders", ""),
            "Funding Stage\t": lead.get("funding_stage", ""),
            "Website URL": lead.get("website_url", ""),
            "LinkedIn URL": lead.get("linkedin_url", ""),
        }
        fields.update({k: v for k, v in extended.items() if v})
        fields = {k: v for k, v in fields.items() if v}
        if "Status" not in fields:
            fields["Status"] = "new"
        record = table.create(fields)
        print(f"[Airtable] Lead created with ID: {record['id']}")
        return record
    except Exception as e:
        error_msg = f"[Airtable] Failed to add lead: {str(e)}"
        print(error_msg)
        raise RuntimeError(error_msg)


def get_all_leads() -> list:
    print("[Airtable] Fetching all leads")
    try:
        table = _get_table()
        records = table.all()
        leads = [{"id": r["id"], **r["fields"]} for r in records]
        print(f"[Airtable] Retrieved {len(leads)} leads")
        return leads
    except Exception as e:
        error_msg = f"[Airtable] Failed to fetch leads: {str(e)}"
        print(error_msg)
        raise RuntimeError(error_msg)


def update_lead_status(record_id: str, status: str) -> dict:
    print(f"[Airtable] Updating record {record_id} status to: {status}")
    try:
        table = _get_table()
        updated = table.update(record_id, {"Status": status})
        print(f"[Airtable] Record {record_id} updated successfully")
        return updated
    except Exception as e:
        error_msg = f"[Airtable] Failed to update lead {record_id}: {str(e)}"
        print(error_msg)
        raise RuntimeError(error_msg)


def search_leads(query: str) -> list:
    print(f"[Airtable] Searching leads for: {query}")
    try:
        all_leads = get_all_leads()
        query_lower = query.lower()
        results = [
            lead for lead in all_leads
            if query_lower in lead.get("Company Name", "").lower()
        ]
        print(f"[Airtable] Found {len(results)} matching leads")
        return results
    except Exception as e:
        error_msg = f"[Airtable] Search failed: {str(e)}"
        print(error_msg)
        raise RuntimeError(error_msg)
