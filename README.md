# tradeAgent

每日盘后自动生成 A 股 / 美股市场总结的网站，支持用户接入自己的 AI 模型（BYOK）做个性化问答。

- 后端：FastAPI + APScheduler + SQLite/PostgreSQL
- 前端：Next.js 14 + TypeScript + Tailwind
- 数据：Tavily 搜索 + Claude 总结
- 部署目标：阿里云

详细实施方案见 `~/.claude/plans/a-agent-skill-shimmying-crane.md`。

## 本地开发

### 后端

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .
copy .env.example .env
# 编辑 .env 填入 TAVILY_API_KEY 和 ANTHROPIC_API_KEY
uvicorn app.main:app --reload
```

后端默认 `http://localhost:8000`，OpenAPI 文档 `/docs`。

### 前端

阶段 2 再加。
