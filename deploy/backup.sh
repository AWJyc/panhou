#!/usr/bin/env bash
# Daily SQLite backup. Drop into /etc/cron.daily/tradeagent-backup
# and `chmod +x`. Default keeps last 14 days locally.
#
# To push to Aliyun OSS, install ossutil and uncomment the OSS_CP block.

set -euo pipefail

DB_PATH=/var/lib/tradeagent/tradeagent.db
BACKUP_DIR=/var/backups/tradeagent
KEEP_DAYS=14

mkdir -p "$BACKUP_DIR"
ts=$(date +%Y%m%d_%H%M%S)
out="$BACKUP_DIR/tradeagent_${ts}.db.gz"

# SQLite online backup (safe even while uvicorn is using the DB)
sqlite3 "$DB_PATH" ".backup '$BACKUP_DIR/tradeagent_${ts}.db'"
gzip "$BACKUP_DIR/tradeagent_${ts}.db"

# Prune
find "$BACKUP_DIR" -name 'tradeagent_*.db.gz' -mtime +${KEEP_DAYS} -delete

# Optional: ship to Aliyun OSS
# ossutil cp "$out" oss://your-bucket/tradeagent-backups/ --config-file /root/.ossutilconfig

echo "[backup] wrote $out"
