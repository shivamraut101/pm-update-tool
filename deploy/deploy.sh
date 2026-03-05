#!/bin/bash
# =============================================================================
# PM Update Tool — VPS Deployment Script
# =============================================================================
# Usage:
#   First time:  chmod +x deploy.sh && ./deploy.sh setup
#   Update app:  ./deploy.sh update
#   Start:       ./deploy.sh start
#   Stop:        ./deploy.sh stop
#   Restart:     ./deploy.sh restart
#   Status:      ./deploy.sh status
#   Logs:        ./deploy.sh logs
#   SSL setup:   ./deploy.sh ssl yourdomain.com
# =============================================================================

set -e

# ── Configuration ──────────────────────────────────────────────────────────
APP_NAME="pm-update-tool"
APP_USER="pm-update-tool"
APP_DIR="/opt/$APP_NAME"
VENV_DIR="$APP_DIR/venv"
REPO_DIR="$APP_DIR/app"
SERVICE_FILE="/etc/systemd/system/$APP_NAME.service"
NGINX_CONF="/etc/nginx/sites-available/$APP_NAME"
NGINX_LINK="/etc/nginx/sites-enabled/$APP_NAME"
PYTHON_VERSION="python3"
PORT=8000

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()  { echo -e "${BLUE}[INFO]${NC} $1"; }
log_ok()    { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# ── Check root ─────────────────────────────────────────────────────────────
check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root (use sudo)"
        exit 1
    fi
}

# ── Install system dependencies ────────────────────────────────────────────
install_dependencies() {
    log_info "Installing system dependencies..."

    # Detect package manager
    if command -v apt-get &> /dev/null; then
        apt-get update -y
        apt-get install -y python3 python3-venv python3-pip nginx git curl certbot python3-certbot-nginx
    elif command -v dnf &> /dev/null; then
        dnf install -y python3 python3-pip nginx git curl certbot python3-certbot-nginx
    elif command -v yum &> /dev/null; then
        yum install -y python3 python3-pip nginx git curl certbot python3-certbot-nginx
    else
        log_error "Unsupported package manager. Install python3, nginx, git, certbot manually."
        exit 1
    fi

    # Install Node.js (for frontend build) if not present
    if ! command -v node &> /dev/null; then
        log_info "Installing Node.js 20.x..."
        curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
        apt-get install -y nodejs 2>/dev/null || dnf install -y nodejs 2>/dev/null || yum install -y nodejs 2>/dev/null
    fi

    log_ok "Dependencies installed"
}

# ── Create app user ────────────────────────────────────────────────────────
create_user() {
    if id "$APP_USER" &>/dev/null; then
        log_info "User '$APP_USER' already exists"
    else
        log_info "Creating user '$APP_USER'..."
        useradd --system --shell /bin/false --home-dir "$APP_DIR" "$APP_USER"
        log_ok "User created"
    fi
}

# ── Setup application directory ────────────────────────────────────────────
setup_app() {
    log_info "Setting up application in $APP_DIR..."

    mkdir -p "$APP_DIR"
    mkdir -p "$REPO_DIR"
    mkdir -p "$APP_DIR/logs"

    # Copy application files (run from project root)
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

    log_info "Copying application files from $PROJECT_ROOT..."
    rsync -av --exclude='venv' --exclude='node_modules' --exclude='.env' \
          --exclude='__pycache__' --exclude='.git' --exclude='tmpclaude*' \
          --exclude='deploy' --exclude='nul' \
          "$PROJECT_ROOT/" "$REPO_DIR/"

    # Setup Python virtual environment
    log_info "Creating Python virtual environment..."
    $PYTHON_VERSION -m venv "$VENV_DIR"
    "$VENV_DIR/bin/pip" install --upgrade pip
    "$VENV_DIR/bin/pip" install -r "$REPO_DIR/requirements.txt"
    log_ok "Python dependencies installed"

    # Build frontend
    if [ -d "$REPO_DIR/frontend" ]; then
        log_info "Building frontend..."
        cd "$REPO_DIR/frontend"
        npm install
        npm run build
        cd -
        log_ok "Frontend built"
    fi

    # Create .env if it doesn't exist
    if [ ! -f "$REPO_DIR/.env" ]; then
        if [ -f "$REPO_DIR/.env.example" ]; then
            cp "$REPO_DIR/.env.example" "$REPO_DIR/.env"
            log_warn ".env created from .env.example — EDIT IT with your secrets!"
            log_warn "  → nano $REPO_DIR/.env"
        fi
    else
        log_info ".env already exists, skipping"
    fi

    # Create uploads directory
    mkdir -p "$REPO_DIR/uploads"

    # Set permissions
    chown -R "$APP_USER:$APP_USER" "$APP_DIR"
    chmod 600 "$REPO_DIR/.env" 2>/dev/null || true

    log_ok "Application setup complete"
}

# ── Install systemd service ────────────────────────────────────────────────
install_service() {
    log_info "Installing systemd service..."

    cat > "$SERVICE_FILE" << EOF
[Unit]
Description=PM Update Tool - Project Management Bot & Dashboard
After=network.target

[Service]
Type=simple
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$REPO_DIR
Environment="PATH=$VENV_DIR/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=$VENV_DIR/bin/uvicorn backend.main:app --host 127.0.0.1 --port $PORT --workers 1
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=$APP_NAME

# Security hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=$REPO_DIR/uploads $APP_DIR/logs

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable "$APP_NAME"
    log_ok "Systemd service installed and enabled"
}

# ── Install Nginx config ──────────────────────────────────────────────────
install_nginx() {
    log_info "Installing Nginx configuration..."

    # Check if domain is configured in .env
    DOMAIN=""
    if [ -f "$REPO_DIR/.env" ]; then
        APP_URL=$(grep -E "^APP_URL=" "$REPO_DIR/.env" | cut -d'=' -f2- | tr -d '[:space:]')
        if [ -n "$APP_URL" ]; then
            DOMAIN=$(echo "$APP_URL" | sed -E 's|https?://||; s|/.*||; s|:.*||')
        fi
    fi

    if [ -z "$DOMAIN" ]; then
        DOMAIN="_"
        log_warn "No APP_URL found in .env — Nginx will listen on server IP"
        log_warn "Set APP_URL in .env and re-run: ./deploy.sh nginx"
    fi

    cat > "$NGINX_CONF" << EOF
server {
    listen 80;
    server_name $DOMAIN;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    # Max upload size (for screenshots)
    client_max_body_size 25M;

    # Proxy to FastAPI
    location / {
        proxy_pass http://127.0.0.1:$PORT;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;

        # Timeouts for long-running webhook/report requests
        proxy_connect_timeout 60s;
        proxy_read_timeout 120s;
        proxy_send_timeout 60s;
    }

    # Serve uploaded files directly via Nginx (faster)
    location /uploads/ {
        alias $REPO_DIR/uploads/;
        expires 7d;
        add_header Cache-Control "public, immutable";
    }

    # Health check (bypass proxy for external monitors)
    location = /api/health {
        proxy_pass http://127.0.0.1:$PORT/api/health;
        access_log off;
    }
}
EOF

    # Enable site
    ln -sf "$NGINX_CONF" "$NGINX_LINK"

    # Remove default site if it exists
    rm -f /etc/nginx/sites-enabled/default 2>/dev/null || true

    # Test & reload
    nginx -t
    systemctl reload nginx
    systemctl enable nginx
    log_ok "Nginx configured for: $DOMAIN"
}

# ── Setup SSL with Let's Encrypt ──────────────────────────────────────────
setup_ssl() {
    local domain="$1"
    if [ -z "$domain" ]; then
        log_error "Usage: ./deploy.sh ssl yourdomain.com"
        exit 1
    fi

    log_info "Setting up SSL for $domain..."

    # Update Nginx server_name first
    sed -i "s/server_name .*/server_name $domain;/" "$NGINX_CONF"
    nginx -t && systemctl reload nginx

    # Run Certbot
    certbot --nginx -d "$domain" --non-interactive --agree-tos --redirect \
        --email "admin@$domain" || {
        log_warn "Certbot with --email failed, trying without..."
        certbot --nginx -d "$domain" --non-interactive --agree-tos --redirect \
            --register-unsafely-without-email
    }

    # Setup auto-renewal
    systemctl enable certbot.timer 2>/dev/null || \
        (crontab -l 2>/dev/null; echo "0 3 * * * certbot renew --quiet") | crontab -

    log_ok "SSL configured for $domain"
    log_info "Certificate will auto-renew"
}

# ── Update application ────────────────────────────────────────────────────
update_app() {
    log_info "Updating application..."

    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

    # Copy updated files (preserve .env)
    rsync -av --exclude='venv' --exclude='node_modules' --exclude='.env' \
          --exclude='__pycache__' --exclude='.git' --exclude='tmpclaude*' \
          --exclude='deploy' --exclude='nul' --exclude='uploads' \
          "$PROJECT_ROOT/" "$REPO_DIR/"

    # Update Python dependencies
    "$VENV_DIR/bin/pip" install -r "$REPO_DIR/requirements.txt"

    # Rebuild frontend if it exists
    if [ -d "$REPO_DIR/frontend" ]; then
        log_info "Rebuilding frontend..."
        cd "$REPO_DIR/frontend"
        npm install
        npm run build
        cd -
    fi

    # Fix permissions
    chown -R "$APP_USER:$APP_USER" "$APP_DIR"

    # Restart service
    systemctl restart "$APP_NAME"
    log_ok "Application updated and restarted"
}

# ── Service management ─────────────────────────────────────────────────────
start_app()   { systemctl start "$APP_NAME"   && log_ok "Started"; }
stop_app()    { systemctl stop "$APP_NAME"    && log_ok "Stopped"; }
restart_app() { systemctl restart "$APP_NAME" && log_ok "Restarted"; }

status_app() {
    echo ""
    systemctl status "$APP_NAME" --no-pager
    echo ""
    log_info "Recent logs:"
    journalctl -u "$APP_NAME" --no-pager -n 20
}

show_logs() {
    journalctl -u "$APP_NAME" -f --no-pager
}

# ── Full setup ─────────────────────────────────────────────────────────────
full_setup() {
    check_root
    log_info "🚀 Full VPS setup for PM Update Tool"
    echo ""

    install_dependencies
    create_user
    setup_app
    install_service
    install_nginx

    echo ""
    log_ok "═══════════════════════════════════════════════════════════"
    log_ok "  Setup complete!"
    log_ok "═══════════════════════════════════════════════════════════"
    echo ""
    log_info "Next steps:"
    echo "  1. Edit your .env file:"
    echo "     nano $REPO_DIR/.env"
    echo ""
    echo "  2. Set APP_URL to your domain (e.g., https://pm.yourdomain.com)"
    echo ""
    echo "  3. Start the service:"
    echo "     sudo ./deploy.sh start"
    echo ""
    echo "  4. Setup SSL (after DNS points to this server):"
    echo "     sudo ./deploy.sh ssl pm.yourdomain.com"
    echo ""
    echo "  5. Check status:"
    echo "     sudo ./deploy.sh status"
    echo ""
}

# ── CLI entrypoint ─────────────────────────────────────────────────────────
case "${1:-help}" in
    setup)    full_setup ;;
    update)   check_root; update_app ;;
    start)    check_root; start_app ;;
    stop)     check_root; stop_app ;;
    restart)  check_root; restart_app ;;
    status)   status_app ;;
    logs)     show_logs ;;
    ssl)      check_root; setup_ssl "$2" ;;
    nginx)    check_root; install_nginx ;;
    *)
        echo ""
        echo "PM Update Tool — VPS Deployment"
        echo ""
        echo "Usage: sudo ./deploy.sh <command>"
        echo ""
        echo "Commands:"
        echo "  setup              Full first-time setup (installs everything)"
        echo "  update             Pull latest code, rebuild, restart"
        echo "  start              Start the application"
        echo "  stop               Stop the application"
        echo "  restart            Restart the application"
        echo "  status             Show service status & recent logs"
        echo "  logs               Follow live logs"
        echo "  ssl <domain>       Setup SSL with Let's Encrypt"
        echo "  nginx              Regenerate Nginx config"
        echo ""
        ;;
esac
