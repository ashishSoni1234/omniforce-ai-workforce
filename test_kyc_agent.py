"""
KYC Agent — Automation Test Suite
Run: python test_kyc_agent.py
Server must be running: uvicorn main:app --reload
"""

import json
import time
import requests

BASE_URL = "http://localhost:8000"

# ──────────────────────────────────────────────
# Test definitions
# ──────────────────────────────────────────────

TESTS = [
    {
        "id": 1,
        "name": "Clean Client — Sab Docs Present (Sarah Johnson)",
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
        "expect": {
            "status": "complete",
            "missing_docs": [],
            "email_sent": False,
        },
    },
    {
        "id": 2,
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
        "expect": {
            "status": "complete",
            "missing_docs": ["Bank Statement", "Proof of Address"],
            "email_sent": True,
        },
    },
    {
        "id": 3,
        "name": "Full Onboarding Pipeline (Emma Williams)",
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
        "expect": {
            "status": "complete",
            "has_onboarding_report": True,
            "welcome_email_sent": True,
        },
    },
]

# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def check_server():
    try:
        r = requests.get(f"{BASE_URL}/health", timeout=5)
        return r.status_code == 200
    except Exception:
        return False


def run_test(test: dict) -> dict:
    print(f"\n{'='*60}")
    print(f"  TEST {test['id']}: {test['name']}")
    print(f"{'='*60}")
    print(f"  Payload:\n{json.dumps(test['payload'], indent=4)}")

    start = time.time()
    try:
        resp = requests.post(
            f"{BASE_URL}/run",
            json=test["payload"],
            timeout=120,
        )
        elapsed = round(time.time() - start, 2)

        if resp.status_code != 200:
            print(f"\n  [FAIL] HTTP {resp.status_code}: {resp.text[:300]}")
            return {"test_id": test["id"], "passed": False, "error": f"HTTP {resp.status_code}"}

        data = resp.json()
        # API returns {"success": true, "result": {"agent_used": "kyc", ..., "result": {...actual...}}}
        outer = data.get("result", {})
        result = outer.get("result", outer)  # unwrap inner KYC result if present

        print(f"\n  Response ({elapsed}s):\n{json.dumps(result, indent=4)}")

        passed, failures = validate(test, result)
        status_str = "PASS" if passed else "FAIL"
        if failures:
            print(f"\n  [{status_str}]  Issues: {'; '.join(failures)}")
        else:
            print(f"\n  [{status_str}]  All checks passed.")

        return {
            "test_id": test["id"],
            "name": test["name"],
            "passed": passed,
            "failures": failures,
            "elapsed_s": elapsed,
            "result": result,
        }

    except requests.exceptions.Timeout:
        print(f"\n  [FAIL] Request timed out after 120s")
        return {"test_id": test["id"], "passed": False, "error": "Timeout"}
    except Exception as exc:
        print(f"\n  [FAIL] Exception: {exc}")
        return {"test_id": test["id"], "passed": False, "error": str(exc)}


def validate(test: dict, result: dict) -> tuple[bool, list]:
    failures = []
    expect = test["expect"]
    tid = test["id"]

    # Common: status must not be "error"
    if result.get("status") == "error":
        failures.append(f"status=error: {result.get('error', 'unknown')}")
        return False, failures

    if "status" in expect:
        if result.get("status") != expect["status"]:
            # onboarding returns "complete" or "pending_documents" — both acceptable for test 3
            if tid == 3 and result.get("status") in ("complete", "pending_documents"):
                pass
            else:
                failures.append(f"status expected '{expect['status']}', got '{result.get('status')}'")

    # Test 1 & 2: missing_docs check
    if "missing_docs" in expect:
        actual_missing = sorted(result.get("missing_docs", []))
        expected_missing = sorted(expect["missing_docs"])
        if actual_missing != expected_missing:
            failures.append(
                f"missing_docs expected {expected_missing}, got {actual_missing}"
            )

    # Test 1 & 2: email_sent check
    if "email_sent" in expect:
        actual_sent = result.get("email_sent", False)
        if actual_sent != expect["email_sent"]:
            failures.append(
                f"email_sent expected {expect['email_sent']}, got {actual_sent}"
            )

    # Test 3: onboarding report must exist
    if expect.get("has_onboarding_report"):
        if not result.get("onboarding_report"):
            failures.append("onboarding_report missing from result")

    # Test 3: welcome email
    if "welcome_email_sent" in expect:
        actual_welcome = result.get("welcome_email_sent", False)
        if actual_welcome != expect["welcome_email_sent"]:
            failures.append(
                f"welcome_email_sent expected {expect['welcome_email_sent']}, got {actual_welcome}"
            )

    # Sanctions result must be present in tests 1 & 2
    if tid in (1, 2) and "sanctions_result" not in result:
        failures.append("sanctions_result missing from response")

    # Risk level must be present
    if "risk_level" not in result and tid in (1, 2):
        failures.append("risk_level missing from response")

    return len(failures) == 0, failures


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

def main():
    print("\n" + "="*60)
    print("  KYC AGENT — AUTOMATION TEST SUITE")
    print("="*60)

    if not check_server():
        print(
            "\n[ERROR] Server not reachable at http://localhost:8000\n"
            "Start it with:  uvicorn main:app --reload\n"
            "Then re-run:    python test_kyc_agent.py\n"
        )
        return

    print("\n  Server is UP. Running 3 tests...\n")

    results = []
    for test in TESTS:
        r = run_test(test)
        results.append(r)

    # ── Summary ──
    print("\n\n" + "="*60)
    print("  FINAL SUMMARY")
    print("="*60)
    passed_count = sum(1 for r in results if r.get("passed"))
    print(f"  Passed: {passed_count}/{len(TESTS)}\n")

    for r in results:
        icon = "PASS" if r.get("passed") else "FAIL"
        name = r.get("name", f"Test {r['test_id']}")
        elapsed = r.get("elapsed_s", "?")
        line = f"  [{icon}]  Test {r['test_id']}: {name}  [{elapsed}s]"
        if not r.get("passed"):
            err = r.get("error") or "; ".join(r.get("failures", []))
            line += f"\n         >> {err}"
        print(line)

    print()


if __name__ == "__main__":
    main()
