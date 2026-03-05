# PM Update Tool

AI-powered project management update tracker with Telegram bot, email reports, and web dashboard.

## 🚀 Quick Start (One Command)

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

That's it! The script will:
- ✅ Create virtual environment (if needed)
- ✅ Install dependencies (if needed)
- ✅ Start the server at http://localhost:8001

## 📋 First-Time Setup

Before running, create a `.env` file in the project root:

```env
# MongoDB Atlas
MONGODB_URI=your-mongodb-uri
MONGODB_DB_NAME=pm_update_tool

# Google Gemini API (paid tier)
GEMINI_API_KEY=your-api-key

# Telegram Bot
TELEGRAM_BOT_TOKEN=your-bot-token
TELEGRAM_CHAT_ID=your-chat-id
MANAGEMENT_TELEGRAM_CHAT_ID=management-chat-id

# Gmail SMTP
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-gmail-app-password
FROM_EMAIL=your-email@gmail.com

# Management Contacts
MANAGEMENT_EMAILS=manager@example.com

# Leave empty for local development
APP_URL=

# API Key
API_KEY=your-random-secret-key
```

See [QUICKSTART.md](QUICKSTART.md) for detailed credential setup.

## 🧪 Testing

Once the server is running:

1. **Open browser**: http://localhost:8001
2. **Telegram bot**: Send `/start` to your bot
3. **Test update**: Send "Yash completed login page on B2B Portal"
4. **Generate report**: Send `/report` command

## 📚 Documentation

- **[QUICKSTART.md](QUICKSTART.md)** - 5-minute setup guide
- **[LOCAL_SETUP.md](LOCAL_SETUP.md)** - Comprehensive setup with troubleshooting
- **[VPS_DEPLOY.md](VPS_DEPLOY.md)** - Deploy to your private VPS

## 🛠️ Tech Stack

- **Backend**: FastAPI + Python 3.13
- **Database**: MongoDB Atlas
- **AI**: Google Gemini (paid tier)
- **Bot**: Telegram Bot API
- **Email**: SMTP (Gmail)
- **Scheduling**: APScheduler

## 🎯 Features

- ✅ Natural language update parsing
- ✅ Telegram bot with commands
- ✅ Screenshot OCR processing
- ✅ Automated daily/weekly reports
- ✅ Email delivery to management
- ✅ Web dashboard
- ✅ Team member tracking
- ✅ Project status monitoring

## 🔧 Manual Setup (If Needed)

```bash
# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (macOS/Linux)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start server
python -m uvicorn backend.main:app --reload --port 8001
```

## 📞 Support

Check the documentation files for troubleshooting:
- Port conflicts
- Telegram bot not responding
- Email sending issues
- MongoDB connection errors
- AI parsing errors

---

**Made with ❤️ for efficient project management**
