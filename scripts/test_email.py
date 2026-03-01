"""Quick test to verify SMTP email sending works."""
import asyncio
import aiosmtplib
from email.mime.text import MIMEText
import os
from dotenv import load_dotenv

load_dotenv()


async def test_send():
    host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER", "")
    password = os.getenv("SMTP_PASSWORD", "")
    from_email = os.getenv("FROM_EMAIL", user)
    to_email = os.getenv("MANAGEMENT_EMAILS", "").split(",")[0].strip()

    if not user or not password:
        print("SMTP_USER and SMTP_PASSWORD must be set in .env")
        return

    if not to_email:
        print("MANAGEMENT_EMAILS must be set in .env")
        return

    msg = MIMEText("This is a test email from PM Update Tool.")
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Subject"] = "PM Update Tool - Test Email"

    try:
        await aiosmtplib.send(
            msg,
            hostname=host,
            port=port,
            start_tls=True,
            username=user,
            password=password,
        )
        print(f"Test email sent to {to_email}")
    except Exception as e:
        print(f"Email failed: {e}")


if __name__ == "__main__":
    asyncio.run(test_send())
