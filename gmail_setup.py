"""
Gmail OAuth Setup — run once to generate token.json
Usage: python gmail_setup.py
"""
from google_auth_oauthlib.flow import InstalledAppFlow
from config.settings import settings

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

flow = InstalledAppFlow.from_client_secrets_file(settings.gmail_credentials_path, SCOPES)
creds = flow.run_local_server(port=8080)

with open(settings.gmail_token_path, "w") as f:
    f.write(creds.to_json())

print(f"[Gmail Setup] Token saved to: {settings.gmail_token_path}")
print("You can now run the KYC agent with full email support.")
