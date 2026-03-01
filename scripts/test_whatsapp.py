"""Quick test to verify Twilio WhatsApp sending works."""
import os
from dotenv import load_dotenv

load_dotenv()


def test_send():
    account_sid = os.getenv("TWILIO_ACCOUNT_SID", "")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN", "")
    from_number = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")
    to_number = os.getenv("USER_WHATSAPP", "")

    if not account_sid or not auth_token:
        print("TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN must be set in .env")
        return

    if not to_number:
        print("USER_WHATSAPP must be set in .env")
        return

    from twilio.rest import Client
    client = Client(account_sid, auth_token)

    try:
        message = client.messages.create(
            body="This is a test message from PM Update Tool.",
            from_=from_number,
            to=f"whatsapp:{to_number}" if not to_number.startswith("whatsapp:") else to_number,
        )
        print(f"Test WhatsApp sent! SID: {message.sid}")
    except Exception as e:
        print(f"WhatsApp failed: {e}")


if __name__ == "__main__":
    test_send()
