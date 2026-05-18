#!/usr/bin/env bash
set -e

ENV=/etc/tradeagent/.env

if ! grep -q '^AUTH_SECRET=' "$ENV"; then
  SECRET=$(openssl rand -hex 32)
  echo "AUTH_SECRET=$SECRET" | sudo tee -a "$ENV" > /dev/null
  echo "added AUTH_SECRET"
fi

if ! grep -q '^BYOK_ENCRYPTION_KEY=' "$ENV"; then
  KEY=$(sudo -u tradeagent /opt/tradeagent/backend/.venv/bin/python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
  echo "BYOK_ENCRYPTION_KEY=$KEY" | sudo tee -a "$ENV" > /dev/null
  echo "added BYOK_ENCRYPTION_KEY"
fi

sudo systemctl restart tradeagent-backend tradeagent-frontend
sleep 4
sudo systemctl status tradeagent-backend --no-pager | head -3
sudo systemctl status tradeagent-frontend --no-pager | head -3
echo "--- last backend log ---"
sudo journalctl -u tradeagent-backend -n 10 --no-pager
