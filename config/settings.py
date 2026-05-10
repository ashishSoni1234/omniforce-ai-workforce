from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    groq_api_key: str
    airtable_api_key: str
    airtable_base_id: str
    airtable_table_name: str = "Leads"
    slack_bot_token: str
    slack_channel_id: str
    gmail_credentials_path: str = "credentials.json"
    gmail_token_path: str = "token.json"
    sender_email: str

    # Optional — AML/KYC real API keys
    opensanctions_api_key: Optional[str] = None   # https://www.opensanctions.org/
    mindee_api_key: Optional[str] = None           # https://platform.mindee.com/

    class Config:
        env_file = ".env"


settings = Settings()
