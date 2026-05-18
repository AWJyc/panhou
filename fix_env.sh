#!/usr/bin/env bash
set -e

REAL=$(openssl rand -hex 32)
sudo sed -i "s|^AUTH_SECRET=.*|AUTH_SECRET=$REAL|" /etc/tradeagent/.env
echo "AUTH_SECRET fixed:"
sudo grep '^AUTH_SECRET=' /etc/tradeagent/.env | head -c 50; echo "..."

sudo systemctl restart tradeagent-backend
sleep 4

TOKEN=$(sudo grep '^ADMIN_REBUILD_TOKEN=' /etc/tradeagent/.env | cut -d= -f2)
echo "trigger jp + kr"
for m in jp kr; do
  curl -s -X POST -H "X-Admin-Token: $TOKEN" "http://127.0.0.1:8000/api/admin/rebuild?market=$m"
  echo
done
