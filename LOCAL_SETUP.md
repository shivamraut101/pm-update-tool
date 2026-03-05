# PM Update Tool - Local Development Setup

## Prerequisites

- Python 3.10+ (tested with 3.13.2)
- Node.js 18+ (optional, only for WhatsApp integration)
- MongoDB Atlas account (already configured)
- Gmail account with App Password (for SMTP)
- Telegram Bot Token (from @BotFather)
- Google Gemini API Key (paid tier)

## Step 1: Python Backend Setup

### 1.1 Create Virtual Environment

```bash
# Navigate to project directory
cd "D:\Personal Projects\Project Managment"

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate

# On macOS/Linux:
source venv/bin/activate
```

### 1.2 Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 1.3 Configure Environment Variables

Copy `.env.example` to `.env` (or create `.env` if it doesn't exist) and fill in your credentials:

```env
# MongoDB (Atlas - already configured)
MONGODB_URI=mongodb+srv://your-connection-string
MONGODB_DB_NAME=pm_update_tool

# Reference DB (read-only)
REF_MONGODB_URI=mongodb+srv://your-ref-connection-string
REF_MONGODB_DB_NAME=live

# Google Gemini API (paid tier)
GEMINI_API_KEY=your-gemini-api-key

# Telegram Bot
TELEGRAM_BOT_TOKEN=your-bot-token-from-botfather
TELEGRAM_CHAT_ID=your-personal-chat-id
MANAGEMENT_TELEGRAM_CHAT_ID=management-chat-id

# SMTP Email (Gmail)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-gmail-app-password
FROM_EMAIL=your-email@gmail.com

# Management Contacts
MANAGEMENT_EMAILS=manager@example.com
MANAGEMENT_CC_EMAILS=optional-cc@example.com

# Alert Emails (sent to you)
ALERT_EMAILS=your-email@gmail.com

# App Config
TIMEZONE=Asia/Kolkata
DAILY_BRIEF_TIME=18:00
WEEKLY_REPORT_DAY=friday
WEEKLY_REPORT_TIME=18:00
REMINDER_NO_UPDATE_TIME=17:00

# Deployment (leave empty for local polling mode)
APP_URL=

# API Key (for cron trigger endpoints)
API_KEY=your-random-secret-key
```

**Important Notes:**

- **APP_URL**: Leave this EMPTY for local development. This enables polling mode (long-polling) for Telegram bot.
- **TELEGRAM_CHAT_ID**: Get this by sending `/start` to your bot and checking the response.
- **MANAGEMENT_TELEGRAM_CHAT_ID**: Get management person's chat ID the same way.
- **SMTP_PASSWORD**: Use Gmail App Password (not your regular password). Generate at: https://myaccount.google.com/apppasswords

### 1.4 Start the Backend Server

```bash
# Make sure virtual environment is activated
python -m uvicorn backend.main:app --reload --port 8001
```

You should see:

```
[telegram] Bot started polling...
[telegram] Bot: @YourBotName
INFO:     Uvicorn running on http://127.0.0.1:8001
```

**Polling Mode:** In local development (when APP_URL is empty), the Telegram bot uses long-polling. It continuously checks for new messages. This is perfect for local testing.

## Step 2: Access the Web Dashboard

Open your browser and go to:

```
http://localhost:8001
```

You should see the PM Update Tool dashboard with:
- Home page
- Updates (view all submitted updates)
- Reports (generate and view reports)
- Settings (view configuration and Telegram commands)

## Step 3: Test Telegram Bot

### 3.1 Get Your Chat ID

1. Open Telegram and search for your bot (username from @BotFather)
2. Send `/start` to the bot
3. The bot will reply with your chat ID
4. Copy this chat ID and add it to `.env` as `TELEGRAM_CHAT_ID`

### 3.2 Get Management Chat ID

1. Have management person open Telegram and send `/start` to your bot
2. Bot replies with their chat ID
3. Copy this and add to `.env` as `MANAGEMENT_TELEGRAM_CHAT_ID`

### 3.3 Send Test Update

Send a message to your bot:

```
Yash completed the login page on B2B Portal.
Shobhit is working on API documentation.
Blocked: Need design approval for dashboard.
```

The bot should:
1. Reply "Processing your update..."
2. Parse the update with AI
3. Reply with parsed information (team members, projects, blockers)

### 3.4 Test Commands

Try these commands:

- `/status` - Quick counts for today
- `/today` - Detailed view of today's parsed updates
- `/pending` - Team members with no updates today
- `/report` - Generate and send daily brief NOW
- `/week` - Generate and send weekly report NOW
- `/undo` - Delete your last update

## Step 4: Test Email Sending (Optional)

Run the test email script:

```bash
python test_email.py
```

This will:
- Show your SMTP configuration
- Send a test email to management
- Print "SUCCESS: Email sent successfully!" if it works

## Step 5: Test Report Generation

### Via Telegram:

Send `/report` to your bot. It will:
1. Generate daily brief
2. Send email to management
3. Send Telegram message to management
4. Reply to you with delivery status

### Via API:

```bash
# Daily brief
curl -X POST "http://localhost:8001/api/reports/generate/daily"

# Weekly report
curl -X POST "http://localhost:8001/api/reports/generate/weekly"
```

### Via Web Dashboard:

1. Go to http://localhost:8001
2. Click "Reports" in navigation
3. Click "Generate Daily Brief" or "Generate Weekly Report"

## Step 6 (Optional): WhatsApp Bridge Setup

**Note:** WhatsApp integration is optional. You can skip this if you only want to use Telegram.

### 6.1 Install Node.js Dependencies

```bash
cd whatsapp-bridge
npm install
```

### 6.2 Configure WhatsApp Bridge

Create `whatsapp-bridge/.env`:

```env
PORT=3001
PM_API_URL=http://localhost:8001
PM_API_KEY=your-api-key-from-main-env
AUTHORIZED_NUMBER=+919876543210
```

### 6.3 Start WhatsApp Bridge

```bash
npm start
```

### 6.4 Scan QR Code

Open browser and go to:

```
http://localhost:3001/qr
```

Scan the QR code with WhatsApp (Settings → Linked Devices → Link a Device)

## Troubleshooting

### Port Already in Use

If port 8001 is already in use:

```bash
# Use a different port
python -m uvicorn backend.main:app --reload --port 8002
```

### Telegram Bot Not Responding

1. Check that `APP_URL` in `.env` is EMPTY (for polling mode)
2. Check bot token is correct
3. Check server logs for errors
4. Restart the server

### Email Not Sending

1. Check Gmail App Password (not regular password)
2. Enable "Less secure app access" if needed
3. Run `python test_email.py` to debug
4. Check SMTP settings in `.env`

### MongoDB Connection Issues

1. Check MongoDB Atlas IP whitelist (allow your IP or use 0.0.0.0/0 for development)
2. Check connection string is correct
3. Verify database user has read/write permissions

### AI Parsing Errors

1. Check `GEMINI_API_KEY` is valid
2. Check you have sufficient quota (paid tier)
3. Check model names in code match available models:
   - `gemini-flash-latest` (default for parsing)
   - `gemini-2.5-flash` (fallback)
   - `gemini-2.5-pro` (for weekly synthesis)

## Development Workflow

### Making Changes

1. Edit code in your IDE
2. Server auto-reloads (because of `--reload` flag)
3. Test via Telegram or web dashboard
4. Check server logs in terminal

### Testing Before Deploy

1. Test all Telegram commands
2. Generate test reports
3. Verify email delivery
4. Check MongoDB data in Atlas dashboard
5. Review logs for errors

### Deploying to VPS

When ready to deploy to your private VPS:

1. Copy the project to your VPS
2. Run the deploy script:
   ```bash
   cd deploy
   chmod +x deploy.sh
   sudo ./deploy.sh setup
   ```
3. Edit `.env` — set `APP_URL` to your domain (e.g., `https://pm.yourdomain.com`)
4. Start the service: `sudo ./deploy.sh start`
5. Setup SSL: `sudo ./deploy.sh ssl pm.yourdomain.com`
6. Bot automatically switches from polling to webhook mode

See [VPS_DEPLOY.md](VPS_DEPLOY.md) for full deployment guide.

## Scheduled Jobs (Local Testing)

The scheduler runs automatically when the backend starts. Default schedule:

- **Daily Brief**: 6:00 PM IST (configurable via `DAILY_BRIEF_TIME`)
- **Weekly Report**: Friday 6:00 PM IST
- **Reminder Check**: 5:00 PM IST

To test scheduled jobs immediately without waiting:

```bash
# Trigger daily report manually
curl -X POST "http://localhost:8001/api/trigger/daily-report?key=your-api-key"

# Trigger weekly report manually
curl -X POST "http://localhost:8001/api/trigger/weekly-report?key=your-api-key"

# Trigger reminder check
curl -X POST "http://localhost:8001/api/trigger/reminder-check?key=your-api-key"
```

## Project Structure

```
D:\Personal Projects\Project Managment\
├── backend/
│   ├── main.py              # FastAPI app entry point
│   ├── config.py            # Settings management
│   ├── database.py          # MongoDB connection
│   ├── routers/
│   │   ├── telegram.py      # Telegram webhook + cron triggers
│   │   ├── reports.py       # Report generation endpoints
│   │   └── ...
│   ├── services/
│   │   ├── ai_parser.py     # Gemini AI parsing
│   │   ├── telegram_bot.py  # Telegram bot logic
│   │   ├── email_sender.py  # SMTP email sending
│   │   ├── report_generator.py  # Report generation
│   │   └── ...
│   └── ...
├── frontend/
│   ├── templates/           # Jinja2 HTML templates
│   └── static/              # CSS, JS, images
├── whatsapp-bridge/         # Optional WhatsApp integration
│   ├── index.js
│   └── package.json
├── venv/                    # Python virtual environment
├── .env                     # Environment variables (NOT in git)
├── requirements.txt         # Python dependencies
├── test_email.py           # Email testing script
└── LOCAL_SETUP.md          # This file
```

## Next Steps

1. Run the backend server
2. Test Telegram bot integration
3. Generate sample reports
4. Review the code and make customizations
5. Deploy to VPS when ready (see deploy/ folder)

## Support

If you encounter issues:

1. Check server logs in terminal
2. Review `.env` configuration
3. Test individual components (email, Telegram, AI)
4. Check MongoDB Atlas dashboard for data
5. Review Gemini API quota and usage

Happy coding! 🚀
