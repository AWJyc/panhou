import logging
import os
from contextlib import asynccontextmanager

# 绕过 Windows 注册表里的系统代理：akshare 调用东方财富的 push2his/push2 子域时
# 经常被代理拦截（"Unable to connect to proxy"）。我们对外的所有出站请求都不走代理。
os.environ.setdefault("NO_PROXY", "*")
os.environ.setdefault("no_proxy", "*")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import admin, auth, health, qa, reports, stocks, user_byok
from app.config import get_settings
from app.db.base import Base
from app.db.migrate import run_migrations
from app.db.session import engine
from app.scheduler.jobs import shutdown_scheduler, start_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    run_migrations(engine)
    start_scheduler()
    try:
        yield
    finally:
        shutdown_scheduler()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="tradeAgent", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=False,
    )

    app.include_router(health.router)
    app.include_router(reports.router)
    app.include_router(admin.router)
    app.include_router(qa.router)
    app.include_router(stocks.router)
    app.include_router(auth.router)
    app.include_router(user_byok.router)
    return app


app = create_app()
