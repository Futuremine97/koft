#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/3d_shoes}"
DOMAIN="${DOMAIN:-koft.app}"
WWW_DOMAIN="${WWW_DOMAIN:-www.koft.app}"
ENABLE_HTTPS="${ENABLE_HTTPS:-0}"
CERTBOT_EMAIL="${CERTBOT_EMAIL:-}"

if ! command -v sudo >/dev/null 2>&1; then
  echo "sudo is required."
  exit 1
fi

if ! command -v apt-get >/dev/null 2>&1; then
  echo "This setup script expects Ubuntu/Debian with apt-get."
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "==> Installing system packages"
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip nginx rsync curl

echo "==> Copying app to $APP_DIR"
sudo mkdir -p "$APP_DIR"
if [ "$SRC_DIR" != "$APP_DIR" ]; then
  sudo rsync -a --delete \
    --exclude ".venv" \
    --exclude "__pycache__" \
    --exclude ".git" \
    --exclude ".DS_Store" \
    "$SRC_DIR/" "$APP_DIR/"
else
  echo "Source is already $APP_DIR; skipping copy."
fi
sudo chown -R "$USER":"$USER" "$APP_DIR"

echo "==> Creating virtualenv and installing Python dependencies"
cd "$APP_DIR"
python3 -m venv .venv
./.venv/bin/pip install --upgrade pip
./.venv/bin/pip install -r requirements.txt

echo "==> Installing systemd service"
sudo cp "$APP_DIR/deploy/footfit-ai.service" /etc/systemd/system/footfit-ai.service
sudo systemctl daemon-reload
sudo systemctl enable footfit-ai
sudo systemctl restart footfit-ai

echo "==> Installing nginx site for $DOMAIN"
sudo cp "$APP_DIR/deploy/koft.app.nginx.conf" /etc/nginx/sites-available/koft.app
sudo ln -sf /etc/nginx/sites-available/koft.app /etc/nginx/sites-enabled/koft.app
if [ -f /etc/nginx/sites-enabled/default ]; then
  sudo rm -f /etc/nginx/sites-enabled/default
fi
sudo nginx -t
sudo systemctl reload nginx

if command -v ufw >/dev/null 2>&1; then
  echo "==> Opening firewall ports if ufw is active"
  sudo ufw allow OpenSSH >/dev/null || true
  sudo ufw allow "Nginx Full" >/dev/null || true
fi

if [ "$ENABLE_HTTPS" = "1" ]; then
  if [ -z "$CERTBOT_EMAIL" ]; then
    echo "CERTBOT_EMAIL is required when ENABLE_HTTPS=1."
    exit 1
  fi
  echo "==> Installing certbot and enabling HTTPS"
  sudo apt-get install -y certbot python3-certbot-nginx
  sudo certbot --nginx \
    -d "$DOMAIN" \
    -d "$WWW_DOMAIN" \
    --non-interactive \
    --agree-tos \
    -m "$CERTBOT_EMAIL" \
    --redirect
fi

echo "==> Verifying local service"
curl -fsS http://127.0.0.1:8000/api/status
echo
echo "Done. Point DNS A record for $DOMAIN to this server public IP, then open:"
echo "  http://$DOMAIN"
if [ "$ENABLE_HTTPS" = "1" ]; then
  echo "  https://$DOMAIN"
fi
