#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────
# deploy.sh — Pull latest code & restart the QuoteApp service
# Run as root (or with sudo) on the VPS:
#   bash /opt/quoteapp/repo/deploy/deploy.sh
# ──────────────────────────────────────────────────────────────────────
set -euo pipefail

APP_DIR="/opt/quoteapp"
REPO_DIR="${APP_DIR}/repo"

echo "==> Pulling latest code..."
cd "${REPO_DIR}"
git pull origin main

echo "==> Installing/updating dependencies..."
"${APP_DIR}/venv/bin/pip" install --upgrade pip
"${APP_DIR}/venv/bin/pip" install -r requirements.txt

echo "==> Restarting service..."
systemctl restart quoteapp

echo "==> Waiting for service to start..."
sleep 2

echo "==> Health check..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/health)
if [ "${HTTP_CODE}" = "200" ]; then
    echo "    OK — health endpoint returned 200"
else
    echo "    WARNING — health endpoint returned ${HTTP_CODE}"
    echo "    Check logs: journalctl -u quoteapp -n 50 --no-pager"
    exit 1
fi

echo ""
echo "Deploy complete."
