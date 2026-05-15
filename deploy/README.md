# 阿里云 ECS 部署指南

最小可行部署：单台 ECS（2c4g 起步，约 ¥60/月）+ nginx + systemd + SQLite。
A 股盘后任务、美股盘后任务全部自动跑。

## 拓扑

```
[Browser]
   │  HTTPS (443 → 80 redirect)
   ▼
[nginx]
   ├─ /api/   → 127.0.0.1:8000  uvicorn + FastAPI + APScheduler
   └─ /       → 127.0.0.1:3000  next start (Next.js prod)
                         │
                         ▼
                  SQLite: /var/lib/tradeagent/tradeagent.db
```

两个 systemd 服务（backend / frontend）+ 一个 nginx vhost。崩了自动起。

## 调度

APScheduler 在 backend 进程内：

| 任务 | 时间（Asia/Shanghai） | 备注 |
|------|----------------------|------|
| A 股盘后 | 周一–周五 15:30 | 15:00 收盘 + 30 分钟缓冲 |
| 美股盘后 | 周二–周六 06:00 | 美东 04:00 收盘（夏令 03:00）+ 2 小时缓冲 |

只要 backend 进程存活，到点自动触发；崩了 systemd 5 秒内重启，下次触发不影响。

---

## 一键安装

```bash
# 1. SSH 到 ECS
ssh root@<your-ecs-ip>

# 2. 在 ECS 上：
git clone https://github.com/YOU/tradeAgent.git /tmp/tradeAgent
sudo DOMAIN=your.domain.com REPO_URL=https://github.com/YOU/tradeAgent.git \
  bash /tmp/tradeAgent/deploy/install.sh

# 3. 填密钥
sudo vi /etc/tradeagent/.env
# 至少填：TAVILY_API_KEY, REPORT_API_KEY, ADMIN_REBUILD_TOKEN

# 4. 重启 backend 加载新 env
sudo systemctl restart tradeagent-backend

# 5. HTTPS（备案完成后）
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your.domain.com
```

完事。打开 `https://your.domain.com` 应该能看到 A 股 + 美股仪表盘。

---

## 手动安装步骤（如果不想用 install.sh）

### 0. ECS 配置建议

- Ubuntu 22.04 LTS（24.04 也行）
- 2c4g 起；CPU 主要给 LLM 调用等待 + APScheduler 内存占用 ~300MB
- 系统盘 40GB 够
- 安全组放行 80/443（备案前可以临时放 8000 用 IP 访问）
- 时区设上海：`sudo timedatectl set-timezone Asia/Shanghai`

### 1. 装系统依赖

```bash
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3.11-dev \
  build-essential pkg-config libxml2-dev libxslt1-dev \
  nginx sqlite3 git curl
# Node 20 (next 14 需要)
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo bash -
sudo apt install -y nodejs
```

### 2. 创建 service 账号 + 目录

```bash
sudo useradd --system --create-home --shell /usr/sbin/nologin tradeagent
sudo mkdir -p /opt/tradeagent /var/lib/tradeagent /etc/tradeagent
sudo chown -R tradeagent:tradeagent /opt/tradeagent /var/lib/tradeagent
sudo chown root:tradeagent /etc/tradeagent && sudo chmod 750 /etc/tradeagent
```

### 3. 拉代码 + 装依赖

```bash
sudo -u tradeagent git clone https://github.com/YOU/tradeAgent.git /opt/tradeagent

# 后端
sudo -u tradeagent bash -c '
  cd /opt/tradeagent/backend
  python3.11 -m venv .venv
  .venv/bin/pip install --upgrade pip wheel
  .venv/bin/pip install -e .
'

# 前端
sudo -u tradeagent bash -c '
  cd /opt/tradeagent/frontend
  npm ci
  npm run build
'
```

### 4. 配 env

```bash
sudo cp /opt/tradeagent/deploy/env.example /etc/tradeagent/.env
sudo chmod 640 /etc/tradeagent/.env
sudo chown root:tradeagent /etc/tradeagent/.env
sudo vi /etc/tradeagent/.env   # 填实际 key
```

### 5. systemd

```bash
sudo cp /opt/tradeagent/deploy/systemd/tradeagent-*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now tradeagent-backend tradeagent-frontend
sudo systemctl status tradeagent-backend tradeagent-frontend
```

### 6. nginx

```bash
# 替换 server_name 后放进 sites-available
sed 's/your\.domain\.com/EX.AMPLE.com/g' /opt/tradeagent/deploy/nginx.conf \
  | sudo tee /etc/nginx/sites-available/tradeagent
sudo ln -sf /etc/nginx/sites-available/tradeagent /etc/nginx/sites-enabled/tradeagent
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

### 7. HTTPS（域名备案后）

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your.domain.com
# 自动续签：certbot 已经装好 systemd timer，systemctl list-timers 能看到
```

---

## 验证

### scheduler 正在跑
```bash
sudo journalctl -u tradeagent-backend -f | grep -E "scheduler|pipeline"
```
启动时应该看到：
```
scheduler started: cn_a@15:30 mon-fri, us@06:00 tue-sat (Asia/Shanghai)
```
到点会自动出现：
```
pipeline start market=cn_a date=2026-05-14
cn_a reasons=113/113 themes=5
pipeline ok market=cn_a date=2026-05-14 report_id=N sectors=10 movers=115
```

### 手动触发（不等定时）

```bash
TOKEN=$(grep ADMIN_REBUILD_TOKEN /etc/tradeagent/.env | cut -d= -f2)
curl -X POST -H "X-Admin-Token: $TOKEN" \
  "https://your.domain.com/api/admin/rebuild?market=cn_a"
```

### 端到端
```bash
curl https://your.domain.com/health
curl https://your.domain.com/api/reports/cn_a/latest | jq .report_date,.status
```

---

## 备份

每天打 SQLite 快照（cron.daily）：

```bash
sudo cp /opt/tradeagent/deploy/backup.sh /etc/cron.daily/tradeagent-backup
sudo chmod +x /etc/cron.daily/tradeagent-backup
# 默认本地保留 14 天，写到 /var/backups/tradeagent/
# 想推 OSS：编辑脚本里的 ossutil cp 那行
```

---

## 更新

```bash
cd /opt/tradeagent
sudo -u tradeagent git pull --ff-only

# 后端有依赖变化时
sudo -u tradeagent bash -c 'cd backend && .venv/bin/pip install -e .'

# 前端有代码变化时
sudo -u tradeagent bash -c 'cd frontend && npm ci && npm run build'

sudo systemctl restart tradeagent-backend tradeagent-frontend
```

---

## 常见坑

| 现象 | 原因 / 处理 |
|------|-------------|
| `pipeline failed market=us no data from any source` | 出站网络问题。akshare 走东方财富 push2，如果阿里云国内节点对某些子域有限速/丢包，看是否有 `Connection aborted` 字样；可以试切香港/新加坡区域。代码里已内置 sina 兜底 |
| Tavily / DeepSeek 调不通 | 国内出口访问海外 API 偶尔超时。Tavily 还好（CDN），DeepSeek 国内可访问。若用 Anthropic 一般需海外节点或走 AnyRouter |
| scheduler 没在跑 | `systemctl status tradeagent-backend`；如果 `Active: inactive` 检查 `/etc/tradeagent/.env` 权限（tradeagent 用户得能读）|
| 前端 404 / 500 | `journalctl -u tradeagent-frontend -f`；通常是 `npm run build` 没跑或代码改完没重启 |
| 节假日空报告 | 当前 MVP 行为：节假日 zt_pool 为空 → 写一条 `status=failed` 报告 + UI 降级显示。要加交易日历跳过的话改 `app/scheduler/jobs.py` |
| 多个 ECS 一起跑 | 别这么干。APScheduler 默认 in-memory，多实例会触发多次。如果需要水平扩展，换成 Celery + Redis 或者把调度抽离到 1 个 worker 单跑 |

---

## 成本估算

| 项 | 月成本（¥） |
|----|-------------|
| ECS 2c4g（突发型 t6） | ~60 |
| 域名（.com 首年） | ~70/年 |
| ICP 备案 | 免费但 ~20 工作日 |
| RDS（可选，SQLite 够用就先不上）| ~100 起 |
| DeepSeek 用量（每天 2 次 LLM 调用 × 30 天）| ~5-10 |
| Tavily 免费额度 | 0 |
| **合计** | **~70-90 / 月** |

备案没下来之前可以先用海外 ECS（香港 / 新加坡），或者前端挂 Vercel 海外预览，后端跑国内 ECS 测调度。
