from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.schemas import ReportListItem, ReportOut
from app.db.models import Market, Report
from app.db.session import get_db

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _validate_market(market: str) -> str:
    if market not in Market.ALL_MVP:
        raise HTTPException(status_code=400, detail=f"unsupported market: {market}")
    return market


@router.get("/today", response_model=list[ReportOut])
def get_today_reports(db: Session = Depends(get_db)) -> list[Report]:
    """Latest available report per MVP market (not strictly today — last generated)."""
    out: list[Report] = []
    for m in Market.ALL_MVP:
        stmt = (
            select(Report)
            .where(Report.market == m)
            .options(selectinload(Report.sectors), selectinload(Report.movers))
            .order_by(Report.report_date.desc())
            .limit(1)
        )
        r = db.execute(stmt).scalar_one_or_none()
        if r is not None:
            out.append(r)
    return out


@router.get("/{market}/latest", response_model=ReportOut)
def get_latest_for_market(
    market: str,
    db: Session = Depends(get_db),
) -> Report:
    _validate_market(market)
    stmt = (
        select(Report)
        .where(Report.market == market)
        .options(selectinload(Report.sectors), selectinload(Report.movers))
        .order_by(Report.report_date.desc())
        .limit(1)
    )
    r = db.execute(stmt).scalar_one_or_none()
    if r is None:
        raise HTTPException(status_code=404, detail="no report yet")
    return r


@router.get("/{market}/{report_date}", response_model=ReportOut)
def get_report_by_date(
    market: str,
    report_date: date,
    db: Session = Depends(get_db),
) -> Report:
    _validate_market(market)
    stmt = (
        select(Report)
        .where(Report.market == market, Report.report_date == report_date)
        .options(selectinload(Report.sectors), selectinload(Report.movers))
    )
    r = db.execute(stmt).scalar_one_or_none()
    if r is None:
        raise HTTPException(status_code=404, detail="report not found")
    return r


@router.get("/{market}", response_model=list[ReportListItem])
def list_reports(
    market: str,
    limit: int = Query(default=30, ge=1, le=180),
    db: Session = Depends(get_db),
) -> list[Report]:
    _validate_market(market)
    stmt = (
        select(Report)
        .where(Report.market == market)
        .order_by(Report.report_date.desc())
        .limit(limit)
    )
    return list(db.execute(stmt).scalars().all())
