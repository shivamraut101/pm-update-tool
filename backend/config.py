from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # MongoDB
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db_name: str = "pm_update_tool"

    # Google Gemini
    gemini_api_key: str = ""

    # Twilio (WhatsApp)
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_whatsapp_from: str = "whatsapp:+14155238886"

    # SMTP (Email)
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    from_email: str = ""

    # App Config
    timezone: str = "Asia/Kolkata"
    daily_brief_time: str = "18:00"
    weekly_report_day: str = "friday"
    weekly_report_time: str = "18:00"
    reminder_no_update_time: str = "17:00"

    # User's WhatsApp
    user_whatsapp: str = ""

    # Management contacts (comma-separated in .env)
    management_emails: str = ""
    management_whatsapp: str = ""

    # Simple API key
    api_key: str = "change_this_to_a_random_string"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    def get_management_emails_list(self) -> List[str]:
        if not self.management_emails:
            return []
        return [e.strip() for e in self.management_emails.split(",") if e.strip()]

    def get_management_whatsapp_list(self) -> List[str]:
        if not self.management_whatsapp:
            return []
        return [n.strip() for n in self.management_whatsapp.split(",") if n.strip()]


settings = Settings()
