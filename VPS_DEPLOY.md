# PM Update Tool — VPS Deployment Guide

Deploy the PM Update Tool on your own private VPS with Nginx, SSL, and systemd.

## Prerequisites

- A VPS with a Linux OS (Ubuntu/Debian recommended)
- A domain name pointing to your VPS IP (for SSL)
- SSH access to the VPS

## Quick Deploy (One Script)

### 1. Upload the project to your VPS

```bash
# From your local machine
scp -r "/path/to/Project Managment" user@your-vps-ip:/tmp/pm-update-tool
```

Or clone from git if you have a repo set up.

### 2. Run the deploy script

```bash
ssh user@your-vps-ip

cd /tmp/pm-update-tool/deploy
chmod +x deploy.sh
sudo ./deploy.sh setup
```

This will:
- Install system dependencies (Python, Node.js, Nginx, Certbot)
- Create a dedicated `pm-update-tool` system user
- Set up the app in `/opt/pm-update-tool/`
- Create Python venv and install dependencies
- Build the React frontend
- Install a systemd service (auto-start on boot)
- Configure Nginx reverse proxy

### 3. Configure environment

```bash
sudo nano /opt/pm-update-tool/app/.env
```

Set all your secrets and **importantly**:
```env
APP_URL=https://pm.yourdomain.com
```

### 4. Start the service

```bash
sudo ./deploy.sh start
```

### 5. Setup SSL (after DNS is pointing to the VPS)

```bash
sudo ./deploy.sh ssl pm.yourdomain.com
```

### 6. Verify

```bash
sudo ./deploy.sh status
curl https://pm.yourdomain.com/api/health
```

---

## Management Commands

All commands from the `deploy/` directory:

| Command | Description |
|---------|-------------|
| `sudo ./deploy.sh setup` | Full first-time setup |
| `sudo ./deploy.sh start` | Start the application |
| `sudo ./deploy.sh stop` | Stop the application |
| `sudo ./deploy.sh restart` | Restart the application |
| `sudo ./deploy.sh status` | Show status & recent logs |
| `sudo ./deploy.sh logs` | Follow live logs (Ctrl+C to exit) |
| `sudo ./deploy.sh update` | Deploy latest code & restart |
| `sudo ./deploy.sh ssl <domain>` | Setup/renew SSL certificate |
| `sudo ./deploy.sh nginx` | Regenerate Nginx config |

## Updating the App

After making code changes locally:

```bash
# Upload updated files to VPS
scp -r "/path/to/Project Managment" user@your-vps-ip:/tmp/pm-update-tool

# On the VPS
cd /tmp/pm-update-tool/deploy
sudo ./deploy.sh update
```

This copies new files (preserving `.env` and uploads), rebuilds frontend, and restarts the service.

## Architecture on VPS

```
Internet
  │
  ▼
Nginx (port 80/443)  ──── SSL termination (Let's Encrypt)
  │
  ▼
FastAPI/Uvicorn (port 8000, localhost only)
  ├── /api/*         → REST API
  ├── /api/telegram/webhook  → Telegram pushes updates here
  ├── /api/trigger/* → Cron trigger endpoints
  ├── /api/health    → Health check
  └── /*             → React SPA (from frontend/dist/)
  │
  ▼
MongoDB Atlas (external)
Telegram API (external)
Resend Email API (external)
```

## Logs & Monitoring

```bash
# Live logs
sudo journalctl -u pm-update-tool -f

# Last 100 lines
sudo journalctl -u pm-update-tool -n 100

# Logs since today
sudo journalctl -u pm-update-tool --since today

# Nginx access logs
sudo tail -f /var/log/nginx/access.log
```

## Firewall Setup (optional but recommended)

```bash
# Allow SSH, HTTP, HTTPS only
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

## Cron Jobs (Optional)

The app has APScheduler built-in for daily/weekly reports. But you can also use external cron as a backup:

```bash
# Add to crontab: sudo crontab -e

# Health check every 5 min (optional monitoring)
*/5 * * * * curl -s https://pm.yourdomain.com/api/health > /dev/null

# Daily report at 6:00 PM IST (backup trigger)
30 12 * * * curl -s -X POST "https://pm.yourdomain.com/api/trigger/daily-report?key=YOUR_API_KEY" > /dev/null

# Weekly report Friday 6:00 PM IST (backup trigger)
30 12 * * 5 curl -s -X POST "https://pm.yourdomain.com/api/trigger/weekly-report?key=YOUR_API_KEY" > /dev/null
```

## Troubleshooting

### Service won't start
```bash
sudo journalctl -u pm-update-tool -n 50 --no-pager
# Check if .env is configured properly
sudo cat /opt/pm-update-tool/app/.env
```

### Nginx 502 Bad Gateway
```bash
# Check if the app is running
sudo systemctl status pm-update-tool
# Check if port 8000 is listening
sudo ss -tlnp | grep 8000
```

### Telegram webhook not working
```bash
# Verify APP_URL is set correctly in .env
# Check webhook status
curl "https://api.telegram.org/bot<YOUR_TOKEN>/getWebhookInfo"
```

### Permission errors
```bash
sudo chown -R pm-update-tool:pm-update-tool /opt/pm-update-tool
sudo chmod 600 /opt/pm-update-tool/app/.env
```
