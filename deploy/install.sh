#!/usr/bin/env bash
# One-shot installer for a fresh Ubuntu 22.04 / 24.04 Aliyun ECS.
# Run as root.  Edit DOMAIN below before invoking.
#
#   curl -fsSL https://your.host/install.sh | DOMAIN=your.domain.com bash
#
# Or after a `git clone` of this repo:
#   sudo DOMAIN=your.domain.com bash deploy/install.sh

set -euo pipefail

DOMAIN="${DOMAIN:-your.domain.com}"
REPO_URL="${REPO_URL:-https://github.com/YOU/tradeAgent.git}"
APP_USER="tradeagent"
APP_DIR=/opt/tradeagent
DATA_DIR=/var/lib/tradeagent
CONF_DIR=/etc/tradeagent

if [[ $EUID -ne 0 ]]; then
  echo "Run as root (sudo)." >&2; exit 1
fi

echo "== [1/9] System packages =="
apt-get update
apt-get install -y \
  python3.11 python3.11-venv python3.11-dev \
  build-essential pkg-config libxml2-dev libxslt1-dev \
  nginx sqlite3 git curl ca-certificates \
  software-properties-common

echo "== [2/9] Node.js 20 =="
if ! command -v node >/dev/null || [[ "$(node -v)" != v20.* ]]; then
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
  apt-get install -y nodejs
fi

echo "== [3/9] System user =="
if ! id "$APP_USER" >/dev/null 2>&1; then
  useradd --system --create-home --shell /usr/sbin/nologin "$APP_USER"
fi

echo "== [4/9] Directories =="
mkdir -p "$APP_DIR" "$DATA_DIR" "$CONF_DIR"
chown -R "$APP_USER":"$APP_USER" "$APP_DIR" "$DATA_DIR"
chown root:"$APP_USER" "$CONF_DIR" && chmod 750 "$CONF_DIR"

echo "== [5/9] Clone repo =="
if [[ ! -d "$APP_DIR/.git" ]]; then
  sudo -u "$APP_USER" git clone "$REPO_URL" "$APP_DIR"
else
  sudo -u "$APP_USER" git -C "$APP_DIR" pull --ff-only
fi

echo "== [6/9] Python venv + deps =="
sudo -u "$APP_USER" bash -c "
  cd $APP_DIR/backend
  python3.11 -m venv .venv
  .venv/bin/pip install --upgrade pip wheel
  .venv/bin/pip install -e .
"

echo "== [7/9] Frontend build =="
sudo -u "$APP_USER" bash -c "
  cd $APP_DIR/frontend
  npm ci
  npm run build
"

echo "== [8/9] Env file =="
if [[ ! -f "$CONF_DIR/.env" ]]; then
  cp "$APP_DIR/deploy/env.example" "$CONF_DIR/.env"
  chmod 640 "$CONF_DIR/.env"
  chown root:"$APP_USER" "$CONF_DIR/.env"
  echo ">>> EDIT $CONF_DIR/.env  with your real keys before continuing!"
  echo ">>> Then run: systemctl restart tradeagent-backend tradeagent-frontend"
fi

echo "== [9/9] systemd + nginx =="
install -m 644 "$APP_DIR/deploy/systemd/tradeagent-backend.service"  /etc/systemd/system/
install -m 644 "$APP_DIR/deploy/systemd/tradeagent-frontend.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now tradeagent-backend tradeagent-frontend

sed "s/your\.domain\.com/$DOMAIN/g" "$APP_DIR/deploy/nginx.conf" \
  > /etc/nginx/sites-available/tradeagent
ln -sf /etc/nginx/sites-available/tradeagent /etc/nginx/sites-enabled/tradeagent
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

echo
echo "── Done. ─────────────────────────────────────────────────"
echo "Edit  $CONF_DIR/.env   then  systemctl restart tradeagent-backend"
echo "HTTPS:   apt install certbot python3-certbot-nginx"
echo "         certbot --nginx -d $DOMAIN"
echo "Health:  curl http://$DOMAIN/health"
echo "Logs:    journalctl -u tradeagent-backend -f"
echo "──────────────────────────────────────────────────────────"
