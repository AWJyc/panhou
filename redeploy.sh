#!/usr/bin/env bash
set -e
cd /opt/tradeagent
sudo -u tradeagent git pull --ff-only
sudo -u tradeagent bash -c 'cd frontend && npm run build' 2>&1 | tail -5
sudo systemctl restart tradeagent-backend tradeagent-frontend
sleep 4

TOKEN=$(sudo grep '^ADMIN_REBUILD_TOKEN=' /etc/tradeagent/.env | cut -d= -f2)
echo "trigger 4 markets"
for m in cn_a jp kr us; do
  curl -s -X POST -H "X-Admin-Token: $TOKEN" "http://127.0.0.1:8000/api/admin/rebuild?market=$m"
  echo
done
