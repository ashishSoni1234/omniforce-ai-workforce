"""
OmniForce — Full Test Suite (Sales + Ops + KYC)
Usage:
  python test_all_agents.py                          # localhost:8000
  python test_all_agents.py https://your.railway.app # Railway URL
"""

import json
import sys
import time
import requests

BASE_URL = (sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://localhost:8000")

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

# ═══════════════════════════════════════════════════════════════════════════════
# TEST DEFINITIONS
# ═══════════════════════════════════════════════════════════════════════════════

SALES_TESTS = [
    {
        "id": "S1",
        "name": "Lead Research — Fintech UK",
        "payload": {
            "agent": "sales",
            "instruction": "Find 3 fintech companies in London with £5M-£50M revenue",
            "context": {},
        },
        "checks": [
            ("status == complete",   lambda r: r.get("status") == "complete"),
            ("leads_added >= 1",     lambda r: int(r.get("leads_added", 0)) >= 1),
            ("companies list present", lambda r: bool(r.get("companies"))),
            ("summary present",      lambda r: bool(r.get("summary"))),
        ],
    },
    {
        "id": "S2",
        "name": "Lead Research — AI Startups Singapore",
        "payload": {
            "agent": "sales",
            "instruction": "Find 3 AI startups in Singapore founded after 2018",
            "context": {},
        },
        "checks": [
            ("status == complete",   lambda r: r.get("status") == "complete"),
            ("leads_added >= 1",     lambda r: int(r.get("leads_added", 0)) >= 1),
        ],
    },
    {
        "id": "S3",
        "name": "Follow-up Email — Draft",
        "payload": {
            "agent": "sales",
            "instruction": "Send a follow-up email to Revolut about partnership",
            "context": {},
        },
        "checks": [
            ("status in sent/drafted", lambda r: r.get("status") in ("sent", "drafted", "complete")),
            ("email_drafted present",  lambda r: bool(r.get("email_drafted") or r.get("response"))),
        ],
    },
    {
        "id": "S4",
        "name": "CRM Update — Status Change",
        "payload": {
            "agent": "sales",
            "instruction": "Update status of Revolut to Contacted in CRM",
            "context": {},
        },
        "checks": [
            ("status present",   lambda r: r.get("status") not in (None, "error")),
        ],
    },
    {
        "id": "S5",
        "name": "Default — Sales Strategy Q&A",
        "payload": {
            "agent": "sales",
            "instruction": "What is the best outreach strategy for B2B SaaS in financial services?",
            "context": {},
        },
        "checks": [
            ("status == complete", lambda r: r.get("status") == "complete"),
            ("response present",   lambda r: bool(r.get("response"))),
        ],
    },
]

OPS_TESTS = [
    {
        "id": "O1",
        "name": "Invoice Processing — Normal Invoice",
        "payload": {
            "agent": "ops",
            "instruction": "Process this invoice and check for anomalies",
            "context": {
                "document": (
                    "Invoice #1042 | Vendor: TechSupplies Ltd | Amount: £12,450.00 | "
                    "Date: 2024-01-15 | Line items: Software licences x10 (£1,245 each) | "
                    "Payment terms: 30 days | VAT: £2,490.00"
                )
            },
        },
        "checks": [
            ("status == complete",       lambda r: r.get("status") == "complete"),
            ("extracted_data present",   lambda r: bool(r.get("extracted_data"))),
            ("has_anomalies key present", lambda r: "has_anomalies" in r),
        ],
    },
    {
        "id": "O2",
        "name": "Invoice Processing — Anomalous Invoice",
        "payload": {
            "agent": "ops",
            "instruction": "Process this invoice and check for anomalies",
            "context": {
                "document": (
                    "Invoice #9999 | Vendor: Unknown Offshore Ltd | Amount: £499,999.00 | "
                    "Date: 2024-01-31 | Line items: Consulting services (vague description) | "
                    "Payment terms: Immediate | No VAT number | Registered address: Cayman Islands"
                )
            },
        },
        "checks": [
            ("status == complete",    lambda r: r.get("status") == "complete"),
            ("anomalies detected",    lambda r: r.get("has_anomalies") is True or bool(r.get("anomaly_report") and r.get("anomaly_report") != "No anomalies detected")),
        ],
    },
    {
        "id": "O3",
        "name": "Approval Routing — High Value",
        "payload": {
            "agent": "ops",
            "instruction": "Route this payment for approval review",
            "context": {"document": "IT infrastructure upgrade. Total: £85,000. Vendor: IBM UK Ltd."},
        },
        "checks": [
            ("status == complete",        lambda r: r.get("status") == "complete"),
            ("routing_decision present",  lambda r: bool(r.get("routing_decision"))),
            ("approval_level == High",    lambda r: r.get("routing_decision", {}).get("approval_level") == "High"),
        ],
    },
    {
        "id": "O4",
        "name": "Approval Routing — Low Value",
        "payload": {
            "agent": "ops",
            "instruction": "Route for approval",
            "context": {"document": "Expense claim: Team lunch £85. Employee: John Smith. Date: 2024-01-20."},
        },
        "checks": [
            ("status == complete",       lambda r: r.get("status") == "complete"),
            ("routing_decision present", lambda r: bool(r.get("routing_decision"))),
            ("approval_level == Low",    lambda r: r.get("routing_decision", {}).get("approval_level") == "Low"),
        ],
    },
    {
        "id": "O5",
        "name": "Report Generation",
        "payload": {
            "agent": "ops",
            "instruction": "Generate a summary report of Q1 2024 financial operations",
            "context": {"document": ""},
        },
        "checks": [
            ("status == complete", lambda r: r.get("status") == "complete"),
            ("report present",     lambda r: bool(r.get("report"))),
            ("report > 100 chars", lambda r: len(r.get("report", "")) > 100),
        ],
    },
    {
        "id": "O6",
        "name": "Default — Ops Q&A",
        "payload": {
            "agent": "ops",
            "instruction": "What are best practices for financial document management?",
            "context": {},
        },
        "checks": [
            ("status == complete", lambda r: r.get("status") == "complete"),
            ("response present",   lambda r: bool(r.get("response"))),
        ],
    },
]

KYC_TESTS = [
    {
        "id": "K1",
        "name": "Clean Client — All Docs (Sarah Johnson)",
        "payload": {
            "agent": "kyc",
            "instruction": "verify and check kyc documents for this client",
            "context": {
                "client_data": {
                    "client_name": "Sarah Johnson",
                    "email": "sarah.johnson@company.com",
                    "documents": ["Passport", "Proof of Address", "Bank Statement"],
                }
            },
        },
        "checks": [
            ("status == complete",       lambda r: r.get("status") == "complete"),
            ("missing_docs == []",       lambda r: r.get("missing_docs") == []),
            ("risk_level present",       lambda r: bool(r.get("risk_level"))),
            ("sanctions_result present", lambda r: bool(r.get("sanctions_result"))),
        ],
    },
    {
        "id": "K2",
        "name": "Missing Docs — Email Trigger (James Mitchell)",
        "payload": {
            "agent": "kyc",
            "instruction": "verify and check kyc documents for this client",
            "context": {
                "client_data": {
                    "client_name": "James Mitchell",
                    "email": "james@example.com",
                    "documents": ["Passport"],
                }
            },
        },
        "checks": [
            ("status == complete",       lambda r: r.get("status") == "complete"),
            ("missing_docs not empty",   lambda r: len(r.get("missing_docs", [])) > 0),
            ("sanctions_result present", lambda r: bool(r.get("sanctions_result"))),
        ],
    },
    {
        "id": "K3",
        "name": "Full Onboarding — Complete Docs (Emma Williams)",
        "payload": {
            "agent": "kyc",
            "instruction": "onboard new client",
            "context": {
                "client_data": {
                    "client_name": "Emma Williams",
                    "email": "emma.williams@firm.com",
                    "documents": ["Passport", "Proof of Address", "Bank Statement"],
                }
            },
        },
        "checks": [
            ("status complete/pending",    lambda r: r.get("status") in ("complete", "pending_documents")),
            ("onboarding_report present",  lambda r: bool(r.get("onboarding_report"))),
            ("sanctions_result present",   lambda r: bool(r.get("sanctions_result"))),
        ],
    },
    {
        "id": "K4",
        "name": "Risk Assessment — High Risk Country",
        "payload": {
            "agent": "kyc",
            "instruction": "assess risk for this client",
            "context": {
                "client_data": {
                    "client_name": "Ahmad Al-Rashid",
                    "country": "Iran",
                    "documents": ["Passport"],
                }
            },
        },
        "checks": [
            ("status == complete",  lambda r: r.get("status") == "complete"),
            ("risk_report present", lambda r: bool(r.get("risk_report"))),
            ("risk_level present",  lambda r: bool(r.get("risk_report", {}).get("risk_level"))),
        ],
    },
    {
        "id": "K5",
        "name": "Onboarding — Incomplete Docs (pending state)",
        "payload": {
            "agent": "kyc",
            "instruction": "onboard new client",
            "context": {
                "client_data": {
                    "client_name": "David Chen",
                    "email": "david.chen@startup.com",
                    "documents": ["Passport"],
                }
            },
        },
        "checks": [
            ("status pending_documents",  lambda r: r.get("status") in ("pending_documents", "complete")),
            ("missing_docs not empty",    lambda r: len(r.get("missing_docs", [])) > 0),
        ],
    },
    {
        "id": "K6",
        "name": "Compliance Q&A — RAG query",
        "payload": {
            "agent": "kyc",
            "instruction": "What are the FATF recommendations for customer due diligence?",
            "context": {"client_data": {}},
        },
        "checks": [
            ("status == complete", lambda r: r.get("status") == "complete"),
            ("response present",   lambda r: bool(r.get("response"))),
        ],
    },
]


# ═══════════════════════════════════════════════════════════════════════════════
# RUNNER
# ═══════════════════════════════════════════════════════════════════════════════

def check_server() -> bool:
    try:
        r = requests.get(f"{BASE_URL}/health", timeout=5)
        return r.status_code == 200
    except Exception:
        return False


def run_test(test: dict) -> dict:
    print(f"\n  {CYAN}{'─'*56}{RESET}")
    print(f"  {BOLD}[{test['id']}] {test['name']}{RESET}")

    start = time.time()
    try:
        resp = requests.post(f"{BASE_URL}/run", json=test["payload"], timeout=120)
        elapsed = round(time.time() - start, 2)

        if resp.status_code != 200:
            print(f"  {RED}[FAIL] HTTP {resp.status_code}: {resp.text[:200]}{RESET}")
            return {"id": test["id"], "name": test["name"], "passed": False,
                    "error": f"HTTP {resp.status_code}", "elapsed": elapsed}

        data = resp.json()
        outer = data.get("result", {})
        result = outer.get("result", outer)

        failures = []
        for label, fn in test["checks"]:
            try:
                ok = fn(result)
            except Exception as e:
                ok = False
                label = f"{label} (exception: {e})"
            if not ok:
                failures.append(label)
                print(f"  {RED}  ✗ {label}{RESET}")
            else:
                print(f"  {GREEN}  ✓ {label}{RESET}")

        passed = len(failures) == 0
        icon = f"{GREEN}[PASS]{RESET}" if passed else f"{RED}[FAIL]{RESET}"
        print(f"  {icon}  {elapsed}s")

        return {"id": test["id"], "name": test["name"], "passed": passed,
                "failures": failures, "elapsed": elapsed}

    except requests.exceptions.Timeout:
        elapsed = round(time.time() - start, 2)
        print(f"  {RED}[FAIL] Timeout after 120s{RESET}")
        return {"id": test["id"], "name": test["name"], "passed": False,
                "error": "Timeout", "elapsed": elapsed}
    except Exception as exc:
        elapsed = round(time.time() - start, 2)
        print(f"  {RED}[FAIL] {exc}{RESET}")
        return {"id": test["id"], "name": test["name"], "passed": False,
                "error": str(exc), "elapsed": elapsed}


def run_suite(label: str, tests: list) -> list:
    print(f"\n{BOLD}{'═'*60}{RESET}")
    print(f"{BOLD}  {label}{RESET}")
    print(f"{BOLD}{'═'*60}{RESET}")
    results = []
    for t in tests:
        results.append(run_test(t))
    return results


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    print(f"\n{BOLD}{'═'*60}")
    print("  OMNIFORCE — FULL AGENT TEST SUITE")
    print(f"  Target: {BASE_URL}")
    print(f"{'═'*60}{RESET}")

    if not check_server():
        print(f"\n{RED}[ERROR] Server not reachable at {BASE_URL}{RESET}")
        print("  Start with:  uvicorn main:app --reload")
        print("  Or pass Railway URL:  python test_all_agents.py https://your.railway.app\n")
        sys.exit(1)

    print(f"\n  {GREEN}Server is UP. Running tests...{RESET}")

    all_results = []
    all_results += run_suite("SALES AGENT  (5 tests)", SALES_TESTS)
    all_results += run_suite("OPS AGENT    (6 tests)", OPS_TESTS)
    all_results += run_suite("KYC AGENT    (6 tests)", KYC_TESTS)

    # ── Final summary ──────────────────────────────────────────────────────────
    total   = len(all_results)
    passed  = sum(1 for r in all_results if r["passed"])
    failed  = total - passed

    print(f"\n{BOLD}{'═'*60}")
    print("  FINAL SUMMARY")
    print(f"{'═'*60}{RESET}")
    print(f"  Total:  {total}   {GREEN}Passed: {passed}{RESET}   {RED}Failed: {failed}{RESET}\n")

    for r in all_results:
        icon  = f"{GREEN}PASS{RESET}" if r["passed"] else f"{RED}FAIL{RESET}"
        extra = ""
        if not r["passed"]:
            err = r.get("error") or " | ".join(r.get("failures", []))
            extra = f"  {YELLOW}>> {err}{RESET}"
        print(f"  [{icon}]  {r['id']:3s}  {r['name']:<45}  {r.get('elapsed','?')}s{extra}")

    print()
    if failed == 0:
        print(f"  {GREEN}{BOLD}All tests passed!{RESET}\n")
    else:
        print(f"  {RED}{BOLD}{failed} test(s) failed.{RESET}\n")


if __name__ == "__main__":
    main()
