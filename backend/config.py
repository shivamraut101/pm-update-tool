from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # MongoDB
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db_name: str = "pm_update_tool"

    # Reference DB (read-only)
    ref_mongodb_uri: str = ""
    ref_mongodb_db_name: str = "live"

    # Google Gemini
    gemini_api_key: str = ""

    # Telegram Bot
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    management_telegram_chat_id: str = ""  # Management person's chat ID for receiving reports

    # Email (Resend API)
    resend_api_key: str = ""
    from_email: str = ""

    # App Config
    timezone: str = "Asia/Kolkata"
    daily_brief_time: str = "18:00"
    weekly_report_day: str = "friday"
    weekly_report_time: str = "18:00"
    reminder_no_update_time: str = "17:00"

    # Management contacts (comma-separated in .env)
    management_emails: str = ""
    management_cc_emails: str = ""

    # Alert emails (sent to the user themselves)
    alert_emails: str = ""
    alert_cc_emails: str = ""

    # Deployment
    app_url: str = "https://pm-update-tool.onrender.com"  # e.g. https://your-app.onrender.com — enables webhook mode

    # Simple API key
    api_key: str = "change_this_to_a_random_string"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

    def get_management_emails_list(self) -> List[str]:
        if not self.management_emails:
            return []
        return [e.strip() for e in self.management_emails.split(",") if e.strip()]

    def get_management_cc_list(self) -> List[str]:
        if not self.management_cc_emails:
            return []
        return [e.strip() for e in self.management_cc_emails.split(",") if e.strip()]

    def get_alert_emails_list(self) -> List[str]:
        if not self.alert_emails:
            return []
        return [e.strip() for e in self.alert_emails.split(",") if e.strip()]

    def get_alert_cc_list(self) -> List[str]:
        if not self.alert_cc_emails:
            return []
        return [e.strip() for e in self.alert_cc_emails.split(",") if e.strip()]


settings = Settings()
