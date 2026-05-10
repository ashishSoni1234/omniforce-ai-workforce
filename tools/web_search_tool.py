from urllib.parse import urlparse
import re


def search_companies(query: str, max_results: int = 5) -> list:
    print(f"[WebSearch] Searching for: {query}")
    try:
        from ddgs import DDGS
        with DDGS() as ddgs:
            raw = list(ddgs.text(query, max_results=max_results))
        results = [
            {"title": r["title"], "url": r["href"], "snippet": r["body"]}
            for r in raw
        ]
        if not results:
            print("[WebSearch] No results returned")
            return []
        print(f"[WebSearch] Found {len(results)} results")
        return results
    except Exception as e:
        print(f"[WebSearch] Error: {str(e)}")
        return []


def get_company_website(company_name: str) -> str:
    """Search for a company's official website and return its URL."""
    print(f"[WebSearch] Finding website for: {company_name}")
    try:
        from ddgs import DDGS
        with DDGS() as ddgs:
            raw = list(ddgs.text(f"{company_name} official website", max_results=3))
        for r in raw:
            url = r.get("href", "")
            parsed = urlparse(url)
            domain = parsed.netloc.replace("www.", "")
            # Skip generic article/list sites
            skip = ["wikipedia", "linkedin", "crunchbase", "tracxn", "yourstory",
                    "inc42", "techcrunch", "forbes", "moneycontrol", "growthschool",
                    "growthjockey", "startupindia", "entrackr"]
            if domain and not any(s in domain for s in skip):
                print(f"[WebSearch] Found website for {company_name}: {url}")
                return url
    except Exception as e:
        print(f"[WebSearch] Website search error for {company_name}: {e}")
    return ""


def get_company_email(company_name: str, company_url: str) -> str:
    """Construct contact email from company's own domain."""
    print(f"[WebSearch] Finding email for: {company_name}")
    # First try from the provided URL
    try:
        if company_url:
            parsed = urlparse(company_url)
            domain = parsed.netloc.replace("www.", "")
            if domain and "." in domain:
                return f"info@{domain}"
    except Exception:
        pass

    # Fallback: search for contact email in snippets
    try:
        from ddgs import DDGS
        with DDGS() as ddgs:
            raw = list(ddgs.text(f"{company_name} contact email", max_results=2))
        for r in raw:
            snippet = r.get("body", "")
            emails = re.findall(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", snippet)
            for email in emails:
                # Skip generic article site emails
                if not any(s in email for s in ["example", "noreply", "test"]):
                    return email
    except Exception as e:
        print(f"[WebSearch] Email search error: {e}")
    return ""


def get_company_revenue(company_name: str) -> str:
    """Search for a company's revenue or valuation."""
    print(f"[WebSearch] Searching revenue for: {company_name}")
    try:
        from ddgs import DDGS
        with DDGS() as ddgs:
            raw = list(ddgs.text(
                f"{company_name} annual revenue OR valuation OR funding 2025 2026",
                max_results=3
            ))
        snippets = " ".join([r.get("body", "") for r in raw])
        return snippets[:1000]
    except Exception as e:
        print(f"[WebSearch] Revenue search error: {e}")
        return ""


def research_company(company_name: str) -> dict:
    print(f"[WebSearch] Researching company: {company_name}")
    try:
        results = search_companies(company_name, max_results=3)
        if not results:
            return {"name": company_name, "description": "No information found", "industry": "Unknown", "url": ""}

        top = results[0]
        snippet = top.get("snippet", "")

        industry = "Technology"
        industry_keywords = {
            "saas": "SaaS", "fintech": "FinTech", "bank": "Banking",
            "insurance": "InsurTech", "invest": "Investment Management",
            "payment": "Payments", "lending": "Lending",
            "crypto": "Cryptocurrency", "accounting": "Accounting",
            "software": "Software", "cloud": "Cloud",
        }
        for keyword, label in industry_keywords.items():
            if keyword.lower() in snippet.lower():
                industry = label
                break

        return {"name": company_name, "description": snippet[:300], "industry": industry, "url": top.get("url", "")}
    except Exception as e:
        print(f"[WebSearch] Failed to research {company_name}: {str(e)}")
        return {"name": company_name, "description": "Research unavailable", "industry": "Unknown", "url": ""}
