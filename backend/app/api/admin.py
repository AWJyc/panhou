from datetime import date as date_cls

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException

from app.config import get_settings
from app.db.models import Market

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _verify_token(token: str | None) -> None:
    settings = get_settings()
    if not token or token != settings.admin_rebuild_token:
        raise HTTPException(status_code=401, detail="invalid admin token")


@router.post("/rebuild")
def rebuild(
    market: str,
    background_tasks: BackgroundTasks,
    report_date: date_cls | None = None,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> dict[str, str]:
    _verify_token(x_admin_token)
    if market not in Market.ALL_MVP:
        raise HTTPException(status_code=400, detail=f"unsupported market: {market}")

    from app.pipeline.runner import run_pipeline_sync

    target_date = report_date or date_cls.today()
    background_tasks.add_task(run_pipeline_sync, market, target_date)
    return {
        "status": "scheduled",
        "market": market,
        "report_date": target_date.isoformat(),
    }


@router.post("/notify-test")
def notify_test(
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> dict[str, str]:
    """发一条测试卡片到飞书，验证 webhook 配置是否正确。"""
    _verify_token(x_admin_token)
    settings = get_settings()
    if not settings.feishu_webhook_url:
        raise HTTPException(status_code=400, detail="FEISHU_WEBHOOK_URL 未配置")
    from app.notify.feishu import send_card

    try:
        send_card(
            settings.feishu_webhook_url,
            title="🛠️ panhou 告警测试",
            content_lines=[
                "**这是一条测试消息**",
                "如果你看到这条卡片，说明 webhook 配置正确。",
                "之后 pipeline 跑完会自动推送成功/失败状态到这个群。",
            ],
            color="blue",
            secret=settings.feishu_webhook_secret or None,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"飞书推送失败: {e}")
    return {"status": "sent"}
