# Quick Start Guide - PM Update Tool Local Development

## 🚀 Run in One Command

**Just double-click or run:**

### Windows (Command Prompt)
```bash
run_local.bat
```

### Windows (PowerShell)
```powershell
.\run_local.ps1
```

### macOS/Linux
```bash
chmod +x run_local.sh
./run_local.sh
```

**That's it!** The script automatically:
- Creates virtual environment (if needed)
- Installs dependencies (if needed)
- Starts server at http://localhost:8001

---

## 📋 First-Time Setup

### Configure `.env` File

Create `.env` file in project root with minimum required configuration:

```env
# MongoDB Atlas
MONGODB_URI=your-mongodb-uri
MONGODB_DB_NAME=pm_update_tool

# Google Gemini (paid tier)
GEMINI_API_KEY=your-gemini-api-key

# Telegram Bot
TELEGRAM_BOT_TOKEN=your-bot-token
TELEGRAM_CHAT_ID=your-chat-id
MANAGEMENT_TELEGRAM_CHAT_ID=management-chat-id

# SMTP (Gmail)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-gmail-app-password
FROM_EMAIL=your-email@gmail.com

# Management Emails
MANAGEMENT_EMAILS=manager@example.com

# Leave empty for local polling mode
APP_URL=

# API Key
API_KEY=your-random-secret-key
```

---

## ✅ After Starting the Server

- **Web Dashboard**: http://localhost:8001
- **Telegram Bot**: Send `/start` to your bot
- **Test Update**: Send message to bot with team updates
- **Generate Report**: Send `/report` command

## Getting Credentials

### Telegram Bot Token

1. Open Telegram and search for `@BotFather`
2. Send `/newbot` and follow instructions
3. Copy the bot token from BotFather's response
4. Paste into `.env` as `TELEGRAM_BOT_TOKEN`

### Your Telegram Chat ID

1. Send `/start` to your bot
2. Bot replies with your chat ID
3. Copy and paste into `.env` as `TELEGRAM_CHAT_ID`

### Gmail App Password

1. Go to https://myaccount.google.com/apppasswords
2. Select "Mail" and your device
3. Generate password
4. Copy 16-character password into `.env` as `SMTP_PASSWORD`

### MongoDB Atlas URI

1. Login to MongoDB Atlas
2. Go to "Database" → "Connect"
3. Choose "Connect your application"
4. Copy connection string
5. Replace `<password>` with your database password
6. Paste into `.env` as `MONGODB_URI`

### Google Gemini API Key

1. Go to https://aistudio.google.com/apikey
2. Create new API key
3. Copy key
4. Paste into `.env` as `GEMINI_API_KEY`

## Common Commands

```bash
# Start server
python -m uvicorn backend.main:app --reload --port 8001

# Test email
python test_email.py

# Generate daily report (API)
curl -X POST "http://localhost:8001/api/reports/generate/daily"

# Generate weekly report (API)
curl -X POST "http://localhost:8001/api/reports/generate/weekly"

# Trigger report with API key
curl -X POST "http://localhost:8001/api/trigger/daily-report?key=your-api-key"
```

## Telegram Bot Commands

Send these to your bot:

- `/start` - Welcome message + get your chat ID
- `/status` - Quick counts for today
- `/today` - Detailed view of today's updates
- `/pending` - Team members with no updates
- `/report` - Generate & send daily brief NOW
- `/week` - Generate & send weekly report NOW
- `/undo` - Delete your last update
- `/help` - Show all commands

## Testing Workflow

1. **Send Test Update** via Telegram:
   ```
   Yash completed login page on B2B Portal.
   Shobhit is working on API documentation.
   ```

2. **Check Parsing** - Bot replies with parsed data

3. **View in Dashboard** - Go to http://localhost:8001/updates

4. **Generate Report** - Send `/report` to bot

5. **Verify Delivery** - Check management email and Telegram

## Troubleshooting

**Bot not responding?**
- Check `APP_URL` in `.env` is EMPTY (for local polling mode)
- Restart server
- Check bot token is correct

**Email not sending?**
- Use Gmail App Password (not regular password)
- Run `python test_email.py` to debug
- Check SMTP settings

**AI errors?**
- Verify Gemini API key is valid
- Check you have sufficient quota (paid tier)
- Check internet connection

**MongoDB errors?**
- Check connection string is correct
- Allow your IP in Atlas (or use 0.0.0.0/0 for dev)
- Verify database user has permissions

## Optional: WhatsApp Bridge

If you need WhatsApp integration:

```bash
cd whatsapp-bridge
npm install
npm start
```

Then visit http://localhost:3001/qr to scan QR code.

**Note:** WhatsApp is optional - Telegram + Email is sufficient for core functionality.

## Need More Details?

See `LOCAL_SETUP.md` for comprehensive setup guide with detailed explanations.

---

**Ready?** Run `python -m uvicorn backend.main:app --reload --port 8001` and start testing! 🚀
