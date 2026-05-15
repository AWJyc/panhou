#!/usr/bin/env bash
# 在 ECS 上执行的增量更新脚本。
# GitHub Actions 通过 SSH 调用它；也可以手动跑 `sudo /opt/tradeagent/deploy/update.sh`。

set -euo pipefail

APP_DIR=/opt/tradeagent
APP_USER=tradeagent

cd "$APP_DIR"

echo "[update] git pull"
prev_sha=$(git rev-parse HEAD)
sudo -u "$APP_USER" git fetch --quiet origin
sudo -u "$APP_USER" git reset --hard origin/main
new_sha=$(git rev-parse HEAD)

if [[ "$prev_sha" == "$new_sha" ]]; then
  echo "[update] no changes (already at $new_sha)"
  exit 0
fi

echo "[update] $prev_sha → $new_sha"
changed=$(git diff --name-only "$prev_sha" "$new_sha")

# 后端依赖变化 → pip install
if echo "$changed" | grep -qE '^backend/(pyproject\.toml|.*\.py)$'; then
  echo "[update] backend changed → pip install"
  sudo -u "$APP_USER" bash -c "
    cd $APP_DIR/backend
    .venv/bin/pip install --quiet -e .
  "
fi

# 前端代码变化 → 重新 build
if echo "$changed" | grep -qE '^frontend/'; then
  echo "[update] frontend changed → npm ci + build"
  sudo -u "$APP_USER" bash -c "
    cd $APP_DIR/frontend
    npm ci --silent
    npm run build
  "
fi

# 重启服务（不管什么变化都重启 backend 让 scheduler 拿到新代码）
echo "[update] restart services"
systemctl restart tradeagent-backend
if echo "$changed" | grep -qE '^frontend/'; then
  systemctl restart tradeagent-frontend
fi

# 健康检查
sleep 3
if curl -fsS http://127.0.0.1:8000/health > /dev/null; then
  echo "[update] ✓ backend healthy"
else
  echo "[update] ✗ backend health check failed" >&2
  systemctl status tradeagent-backend --no-pager | tail -20 >&2
  exit 1
fi

echo "[update] done at $(date -Iseconds)"
