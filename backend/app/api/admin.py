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
