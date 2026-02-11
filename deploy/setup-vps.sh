#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────
# setup-vps.sh — One-time server setup for TheEasy.AI QuoteApp API
# Run as root on a fresh Ubuntu 22.04/24.04 Hostinger VPS:
#   scp deploy/setup-vps.sh root@<VPS_IP>:/root/
#   ssh root@<VPS_IP> bash /root/setup-vps.sh
# ──────────────────────────────────────────────────────────────────────
set -euo pipefail

APP_USER="quoteapp"
APP_DIR="/opt/quoteapp"
REPO_URL="https://github.com/cassiano-ai/TheEasy.AI-Python.git"
DOMAIN="api.aibreslow.com"

echo "==> Updating system packages..."
apt-get update && apt-get upgrade -y

# ── Python 3.12 ──────────────────────────────────────────────────────
echo "==> Installing Python 3.12..."
apt-get install -y software-properties-common
add-apt-repository -y ppa:deadsnakes/ppa
apt-get update
apt-get install -y python3.12 python3.12-venv python3.12-dev

# ── Nginx + Certbot ──────────────────────────────────────────────────
echo "==> Installing Nginx and Certbot..."
apt-get install -y nginx certbot python3-certbot-nginx

# ── Git ──────────────────────────────────────────────────────────────
apt-get install -y git curl

# ── Create app user (no login shell, home = APP_DIR) ─────────────────
echo "==> Creating app user '${APP_USER}'..."
if ! id "${APP_USER}" &>/dev/null; then
    useradd --system --shell /usr/sbin/nologin --home-dir "${APP_DIR}" "${APP_USER}"
fi

# ── Create app directory ─────────────────────────────────────────────
echo "==> Setting up ${APP_DIR}..."
mkdir -p "${APP_DIR}/data"
git clone "${REPO_URL}" "${APP_DIR}/repo"

# ── Python venv + dependencies ───────────────────────────────────────
echo "==> Creating Python venv and installing dependencies..."
python3.12 -m venv "${APP_DIR}/venv"
"${APP_DIR}/venv/bin/pip" install --upgrade pip
"${APP_DIR}/venv/bin/pip" install -r "${APP_DIR}/repo/requirements.txt"

# ── Environment file ─────────────────────────────────────────────────
echo "==> Copying .env.production template..."
cp "${APP_DIR}/repo/deploy/.env.production" "${APP_DIR}/.env"
chown -R "${APP_USER}:${APP_USER}" "${APP_DIR}"

# ── systemd service ──────────────────────────────────────────────────
echo "==> Installing systemd service..."
cp "${APP_DIR}/repo/deploy/quoteapp.service" /etc/systemd/system/quoteapp.service
systemctl daemon-reload
systemctl enable quoteapp

# ── Nginx config ─────────────────────────────────────────────────────
echo "==> Configuring Nginx..."
cp "${APP_DIR}/repo/deploy/nginx-api.conf" "/etc/nginx/sites-available/${DOMAIN}"
ln -sf "/etc/nginx/sites-available/${DOMAIN}" "/etc/nginx/sites-enabled/${DOMAIN}"
# Remove default site if it exists
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx

# ── Firewall ─────────────────────────────────────────────────────────
echo "==> Configuring firewall..."
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw --force enable

echo ""
echo "============================================================"
echo "  Setup complete!"
echo "============================================================"
echo ""
echo "Next steps:"
echo "  1. Edit /opt/quoteapp/.env with your real secrets"
echo "  2. Make sure DNS A record points ${DOMAIN} to this server"
echo "  3. Start the service:"
echo "       systemctl start quoteapp"
echo "  4. Verify locally:"
echo "       curl http://localhost:8000/api/v1/health"
echo "  5. Get SSL certificate:"
echo "       certbot --nginx -d ${DOMAIN}"
echo "  6. Verify HTTPS:"
echo "       curl https://${DOMAIN}/api/v1/health"
echo ""
