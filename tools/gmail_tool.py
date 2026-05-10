import os
import base64
from email.mime.text import MIMEText
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from config.settings import settings

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


def get_gmail_service():
    print("[Gmail] Initializing Gmail service")
    try:
        creds = None
        token_path = settings.gmail_token_path
        credentials_path = settings.gmail_credentials_path

        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
            print("[Gmail] Loaded credentials from token file")

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                print("[Gmail] Refreshing expired credentials")
                creds.refresh(Request())
            else:
                # Non-interactive environment — raise instead of blocking on browser OAuth.
                # Run  python gmail_setup.py  once to generate token.json.
                raise RuntimeError(
                    "Gmail token.json not found. Run `python gmail_setup.py` to authenticate."
                )

            with open(token_path, "w") as token_file:
                token_file.write(creds.to_json())
                print(f"[Gmail] Token saved to {token_path}")

        service = build("gmail", "v1", credentials=creds)
        print("[Gmail] Service initialized successfully")
        return service
    except Exception as e:
        error_msg = f"[Gmail] Failed to initialize service: {str(e)}"
        print(error_msg)
        raise RuntimeError(error_msg)


def send_email(to: str, subject: str, body: str) -> dict:
    print(f"[Gmail] Sending email to: {to} | Subject: {subject}")
    try:
        service = get_gmail_service()
        message = MIMEText(body)
        message["to"] = to
        message["from"] = settings.sender_email
        message["subject"] = subject

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        send_result = service.users().messages().send(
            userId="me", body={"raw": raw}
        ).execute()

        print(f"[Gmail] Email sent successfully. Message ID: {send_result.get('id')}")
        return {"status": "sent", "to": to, "subject": subject, "message_id": send_result.get("id")}
    except Exception as e:
        error_msg = f"[Gmail] Failed to send email to {to}: {str(e)}"
        print(error_msg)
        raise RuntimeError(error_msg)


def draft_followup_email(company_name: str, contact_name: str) -> str:
    print(f"[Gmail] Drafting follow-up email for {company_name} / {contact_name}")
    template = f"""Subject: Following Up — Partnership Opportunity with OmniForce AI

Dear {contact_name},

I hope this message finds you well.

I'm reaching out to follow up on our recent conversation regarding how OmniForce AI can support {company_name}'s growth objectives. Our autonomous AI workforce platform is specifically designed for financial services organisations looking to streamline operations, accelerate compliance, and scale their sales pipeline — without adding headcount.

We've helped firms similar to {company_name} reduce operational overhead by up to 40% while improving compliance accuracy. I believe there's a strong fit here.

I'd love to schedule a 20-minute call at your earliest convenience to explore how we can tailor our solution to your specific needs.

Please feel free to reply to this email or book a slot directly using the link below.

Looking forward to connecting.

Warm regards,
OmniForce AI Partnerships Team
partnerships@omniforce.ai
"""
    return template
