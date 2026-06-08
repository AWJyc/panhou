"""End-to-end pipeline: fetch → summarize → persist.

Idempotent on (market, report_date): re-running overwrites the previous report.
Failures don't crash; they write a Report with status='failed' so the UI can
degrade gracefully and the next scheduled run will retry.

A 股专用路径：先用 akshare 拉结构化涨停板池（authoritative），再用 Tavily 拿
新闻叙事，LLM 只负责综述和板块，不再产 movers，避免幻觉。
"""

import asyncio
import logging
import time
from datetime import date, datetime, timezone

from sqlalchemy import select

from app.db.models import MarketMover, MarketSector, Report
from app.db.session import SessionLocal
from app.pipeline.trading_calendar import is_trading_day
from app.pipeline.cn_a_data import (
    fetch_a_indices,
    fetch_concept_boards,
    fetch_industry_boards,
    fetch_limit_down_pool,
    fetch_limit_up_pool,
    summarize_boards_for_llm,
    summarize_pool_for_llm,
)
from app.pipeline.market_queries import build_queries
from app.pipeline.summarizer import generate_limit_up_reasons, summarize
from app.pipeline.tavily_client import dedupe_and_compact, search_many
from app.pipeline.jp_kr_data import (
    build_movers_from_basket,
    build_sectors_from_basket,
    fetch_jp_basket,
    fetch_jp_indices,
    fetch_kr_basket,
    fetch_kr_indices,
    summarize_overseas_for_llm,
)
from app.pipeline.us_data import (
    fetch_us_indices,
    fetch_us_sectors,
    fetch_us_top_movers,
    summarize_us_for_llm,
)

log = logging.getLogger(__name__)


async def run_pipeline(market: str, report_date: date, *, force: bool = False) -> int:
    """跑 market 的 pipeline。

    force=False 时若 report_date 是该 market 的非交易日 → 跳过（不入库不通知），return -1。
    force=True 用于手动 rebuild 想强制跑（补数据/调试）。
    """
    if not force and not is_trading_day(market, report_date):
        log.info("pipeline skipped (non-trading day) market=%s date=%s", market, report_date)
        return -1

    log.info("pipeline start market=%s date=%s force=%s", market, report_date, force)
    started = time.monotonic()
    forced_status: str | None = None
    err_msg: str | None = None
    try:
        if market == "cn_a":
            report_id = await _run_cn_a(report_date)
        elif market == "us":
            report_id = await _run_us(report_date)
        elif market == "jp":
            report_id = await _run_jp(report_date)
        elif market == "kr":
            report_id = await _run_kr(report_date)
        else:
            report_id = await _run_default(market, report_date)
    except Exception as e:
        log.exception("pipeline failed market=%s date=%s", market, report_date)
        report_id = _persist_failed(market, report_date, str(e), None)
        forced_status = "failed"
        err_msg = f"{type(e).__name__}: {e}"

    elapsed = time.monotonic() - started
    _notify_safe(market, report_date, report_id, elapsed, forced_status, err_msg)
    _prune_safe(market)
    return report_id


def _prune_safe(market: str) -> None:
    """跑完后裁剪该市场历史，只保留最近 N 个交易日。异常吞掉不影响主流程。"""
    try:
        from app.config import get_settings
        from app.pipeline.retention import prune_market_history

        prune_market_history(market, keep=get_settings().report_retention_days)
    except Exception as e:
        log.warning("retention prune 异常 (吞掉): %s", e)


def _notify_safe(
    market: str,
    report_date: date,
    report_id: int,
    elapsed: float,
    forced_status: str | None,
    error: str | None,
) -> None:
    try:
        from app.notify.notifier import notify_pipeline_done

        notify_pipeline_done(
            market,
            report_date,
            report_id,
            elapsed_sec=elapsed,
            forced_status=forced_status,
            error=error,
        )
    except Exception as e:
        log.warning("notify hook 异常 (吞掉): %s", e)


def run_pipeline_sync(market: str, report_date: date, *, force: bool = False) -> int:
    return asyncio.run(run_pipeline(market, report_date, force=force))


async def _run_jp(report_date: date) -> int:
    return await _run_overseas(
        market="jp", label="日股", report_date=report_date,
        fetch_idx=fetch_jp_indices, fetch_basket=fetch_jp_basket,
    )


async def _run_kr(report_date: date) -> int:
    return await _run_overseas(
        market="kr", label="韩股", report_date=report_date,
        fetch_idx=fetch_kr_indices, fetch_basket=fetch_kr_basket,
    )


async def _run_overseas(
    market: str,
    label: str,
    report_date: date,
    fetch_idx,
    fetch_basket,
) -> int:
    """日/韩股通用：指数 + 精选大盘股篮子（Yahoo）给权威涨跌幅，LLM 只写综述 + 板块 note。

    篮子全挂时降级回老路（sectors/movers 由 LLM 从 Tavily 提取）。
    """
    queries = build_queries(market, report_date)
    indices, basket, batches = await asyncio.gather(
        fetch_idx(),
        fetch_basket(),
        search_many(queries, max_results=8),
    )
    sources = dedupe_and_compact(batches)

    if not indices and not basket and not sources:
        return _persist_failed(market, report_date, "no data from any source", batches)

    # report_date 用 indices 实际数据日（避免 UTC vs Asia/Shanghai 跨日导致重复 row）
    real_dates = [str(i.get("date") or "")[:10] for i in indices if i.get("date")]
    if real_dates:
        try:
            report_date = date.fromisoformat(max(real_dates))
        except ValueError:
            pass

    sectors_data = build_sectors_from_basket(basket)
    gainers, losers = build_movers_from_basket(basket)
    digest = summarize_overseas_for_llm(label, indices, sectors_data, gainers, losers)
    log.info(
        "%s data: indices=%d basket=%d sectors=%d gainers=%d losers=%d tavily_sources=%d",
        market,
        len(indices),
        len(basket),
        len(sectors_data),
        len(gainers),
        len(losers),
        len(sources),
    )

    # 即使 LLM 失败也要保住 indices/篮子数据，让前端至少能显示
    try:
        structured, model_id = summarize(
            market, report_date, sources, pool_digest=digest or None
        )
    except Exception as e:
        log.error("%s summarize failed (keeping structured data): %s", market, e)
        structured = {"summary_md": f"LLM 综述失败：{type(e).__name__}", "sectors": [], "movers": []}
        model_id = ""

    # sectors：篮子有数据时用权威涨跌幅，note 走 LLM 输出按名称模糊匹配；否则降级回 LLM
    llm_sector_notes = {
        (s.get("name") or "").strip(): str(s.get("note", ""))
        for s in (structured.get("sectors") or [])
        if (s.get("name") or "").strip()
    }

    def _lookup_note(target: str) -> str:
        if target in llm_sector_notes:
            return llm_sector_notes[target]
        for k, v in llm_sector_notes.items():
            if target in k or k in target:
                return v
        return ""

    if sectors_data:
        sectors = [
            MarketSector(
                name=s["name"],
                change_pct=round(s["change_pct"], 2),
                note=_lookup_note(s["name"]),
            )
            for s in sectors_data
        ]
    else:
        sectors = _build_sectors(structured.get("sectors") or [])

    # movers：篮子有数据时用权威涨跌榜；否则降级回 LLM
    if gainers or losers:
        movers = [
            MarketMover(
                symbol=g["symbol"][:32], name=g["name"][:64],
                move_type="top_gainer", change_pct=g.get("change_pct"), note="",
            )
            for g in gainers
        ] + [
            MarketMover(
                symbol=lo["symbol"][:32], name=lo["name"][:64],
                move_type="top_loser", change_pct=lo.get("change_pct"), note="",
            )
            for lo in losers
        ]
    else:
        movers = _build_movers_from_llm(structured.get("movers") or [])

    raw_payload = {
        "tavily_sources": sources,
        "indices": indices,
        "basket_count": len(basket),
        "digest": digest,
    }
    return _persist(
        market,
        report_date,
        summary_md=structured.get("summary_md", ""),
        sources=raw_payload,
        model_id=model_id,
        sectors=sectors,
        movers=movers,
        indices=indices,
    )


async def _run_default(market: str, report_date: date) -> int:
    queries = build_queries(market, report_date)
    batches = await search_many(queries, max_results=8)
    sources = dedupe_and_compact(batches)

    if not sources:
        return _persist_failed(market, report_date, "no search results", batches)

    structured, model_id = summarize(market, report_date, sources)
    movers_from_llm = _build_movers_from_llm(structured.get("movers") or [])
    sectors = _build_sectors(structured.get("sectors") or [])
    return _persist(
        market,
        report_date,
        summary_md=structured.get("summary_md", ""),
        sources=sources,
        model_id=model_id,
        sectors=sectors,
        movers=movers_from_llm,
    )


async def _run_cn_a(report_date: date) -> int:
    # 并发跑：涨停板池、跌停板池、行业板块、概念板块、三大指数、Tavily 新闻
    queries = build_queries("cn_a", report_date)
    zt_pool, dt_pool, industries, concepts, indices, batches = await asyncio.gather(
        fetch_limit_up_pool(report_date),
        fetch_limit_down_pool(report_date),
        fetch_industry_boards(),
        fetch_concept_boards(),
        fetch_a_indices(),
        search_many(queries, max_results=8),
    )
    sources = dedupe_and_compact(batches)

    if not zt_pool and not dt_pool and not industries and not sources:
        return _persist_failed("cn_a", report_date, "no data from any source", batches)

    # 用 indices 实际数据日推算 report_date，避免盘前/手动触发时
    # report_date 写"今天"、但 indices 实际是上个交易日"昨天" 的错位
    real_dates = [str(i.get("date") or "")[:10] for i in indices if i.get("date")]
    if real_dates:
        try:
            real = date.fromisoformat(max(real_dates))
            if real != report_date:
                log.info("cn_a report_date adjusted: %s → %s (per indices)", report_date, real)
            report_date = real
        except ValueError:
            pass

    pool_digest_parts = [
        summarize_pool_for_llm(zt_pool, dt_pool),
        summarize_boards_for_llm(industries, concepts),
    ]
    pool_digest = "\n\n".join(p for p in pool_digest_parts if p)

    log.info(
        "cn_a data: zt=%d dt=%d industries=%d concepts=%d indices=%d tavily_sources=%d",
        len(zt_pool),
        len(dt_pool),
        len(industries),
        len(concepts),
        len(indices),
        len(sources),
    )

    # LLM 只负责 summary + sectors（movers 强制空）
    structured, model_id = summarize("cn_a", report_date, sources, pool_digest=pool_digest)

    raw_sectors = structured.get("sectors") or []
    _patch_sector_pcts(raw_sectors, industries, concepts)
    sectors = _build_sectors(raw_sectors)

    # 第二次 LLM 调用：批量生成每只涨停股的「涨停原因」+ 主题聚类
    reasons_map, themes_out, _reason_model = generate_limit_up_reasons(
        report_date, zt_pool, industries, concepts, sources
    )
    log.info(
        "cn_a reasons=%d/%d themes=%d",
        len(reasons_map),
        len(zt_pool),
        len(themes_out),
    )

    movers: list[MarketMover] = []
    for s in zt_pool:
        info = reasons_map.get(s["symbol"], {})
        movers.append(
            MarketMover(
                symbol=s["symbol"][:32],
                name=s["name"][:64],
                move_type="limit_up",
                change_pct=s.get("change_pct"),
                limit_up_streak=s.get("limit_up_streak"),
                concept=(s.get("concept") or None),
                sealing_amount=s.get("sealing_amount"),
                note=info.get("reason", "") if isinstance(info, dict) else "",
            )
        )
    for s in dt_pool:
        movers.append(
            MarketMover(
                symbol=s["symbol"][:32],
                name=s["name"][:64],
                move_type="limit_down",
                change_pct=s.get("change_pct"),
                concept=(s.get("concept") or None),
                note="",
            )
        )

    raw_payload = {
        "tavily_sources": sources,
        "zt_pool_count": len(zt_pool),
        "dt_pool_count": len(dt_pool),
        "industries_count": len(industries),
        "concepts_count": len(concepts),
        "pool_digest": pool_digest,
    }
    report_id = _persist(
        "cn_a",
        report_date,
        summary_md=structured.get("summary_md", ""),
        sources=raw_payload,
        model_id=model_id,
        sectors=sectors,
        movers=movers,
        indices=indices,
        themes=themes_out,
    )

    # 预热涨停股 sparkline 缓存，让前端打开页面瞬间命中
    try:
        from app.api.stocks import prewarm_cn_a_sparklines

        symbols = [s["symbol"] for s in zt_pool if s.get("symbol")]
        await prewarm_cn_a_sparklines(symbols, report_date.isoformat())
    except Exception as e:
        log.warning("sparkline prewarm 失败（不影响 pipeline）: %s", e)

    return report_id


def _patch_sector_pcts(
    sectors: list[dict],
    industries: list[dict],
    concepts: list[dict],
) -> None:
    """如果 LLM 没给 change_pct，从 akshare 行业/概念板块按名称匹配兜底。

    in-place mutation. 名称匹配：精确 → 含子串。
    """
    lookup: dict[str, float] = {}
    for b in industries + concepts:
        pct = b.get("change_pct")
        if pct is None:
            continue
        lookup[b["name"]] = pct

    for s in sectors:
        if s.get("change_pct") is not None:
            continue
        name = (s.get("name") or "").strip()
        if not name:
            continue
        if name in lookup:
            s["change_pct"] = lookup[name]
            continue
        # 子串匹配（名称差异如 "光伏" vs "光伏设备"）
        for k, v in lookup.items():
            if name in k or k in name:
                s["change_pct"] = v
                break


async def _run_us(report_date: date) -> int:
    queries = build_queries("us", report_date)
    indices, sectors_data, movers_data, batches = await asyncio.gather(
        fetch_us_indices(),
        fetch_us_sectors(),
        fetch_us_top_movers(),
        search_many(queries, max_results=8),
    )
    gainers, losers = movers_data
    sources = dedupe_and_compact(batches)

    if not indices and not sectors_data and not gainers and not sources:
        return _persist_failed("us", report_date, "no data from any source", batches)

    # 美股 report_date 用 indices 实际数据日，避免「任务跑的那天 != 美股交易日」造成重复 row
    real_dates: list[str] = []
    for i in indices:
        d = i.get("date")
        if d:
            real_dates.append(str(d)[:10])
    for s in sectors_data:
        d = s.get("date")
        if d:
            real_dates.append(str(d)[:10])
    if real_dates:
        try:
            report_date = date.fromisoformat(max(real_dates))
            log.info("us pipeline real_data_date=%s", report_date)
        except ValueError:
            pass

    digest = summarize_us_for_llm(indices, sectors_data, gainers, losers)
    log.info(
        "us data: indices=%d sectors=%d gainers=%d losers=%d tavily_sources=%d",
        len(indices),
        len(sectors_data),
        len(gainers),
        len(losers),
        len(sources),
    )

    structured, model_id = summarize("us", report_date, sources, pool_digest=digest)

    # Sectors 直接用 ETF 数据（authoritative），note 走 LLM 输出做名称模糊匹配
    llm_sector_notes = {
        (s.get("name") or "").strip(): str(s.get("note", ""))
        for s in (structured.get("sectors") or [])
        if (s.get("name") or "").strip()
    }

    def _lookup_note(target: str) -> str:
        if target in llm_sector_notes:
            return llm_sector_notes[target]
        for k, v in llm_sector_notes.items():
            if target in k or k in target:
                return v
        return ""

    sectors: list[MarketSector] = []
    for s in sectors_data:
        sectors.append(
            MarketSector(
                name=s["name"],
                change_pct=s.get("change_pct"),
                note=_lookup_note(s["name"]),
            )
        )

    movers: list[MarketMover] = []
    for g in gainers:
        movers.append(
            MarketMover(
                symbol=g["symbol"][:32],
                name=g["name"][:64],
                move_type="top_gainer",
                change_pct=g.get("change_pct"),
                note="",
            )
        )
    for lo in losers:
        movers.append(
            MarketMover(
                symbol=lo["symbol"][:32],
                name=lo["name"][:64],
                move_type="top_loser",
                change_pct=lo.get("change_pct"),
                note="",
            )
        )

    raw_payload = {
        "tavily_sources": sources,
        "indices": indices,
        "sectors_count": len(sectors_data),
        "gainers_count": len(gainers),
        "losers_count": len(losers),
        "digest": digest,
    }
    return _persist(
        "us",
        report_date,
        summary_md=structured.get("summary_md", ""),
        sources=raw_payload,
        model_id=model_id,
        sectors=sectors,
        movers=movers,
        indices=indices,
    )


def _build_sectors(items: list[dict]) -> list[MarketSector]:
    return [
        MarketSector(
            name=str(s.get("name", ""))[:64],
            change_pct=s.get("change_pct"),
            note=str(s.get("note", "")),
        )
        for s in items
    ]


def _build_movers_from_llm(items: list[dict]) -> list[MarketMover]:
    return [
        MarketMover(
            symbol=str(m.get("symbol") or "")[:32],
            name=str(m.get("name", ""))[:64],
            move_type=str(m.get("move_type", "top_gainer")),
            change_pct=m.get("change_pct"),
            note=str(m.get("note", "")),
        )
        for m in items
    ]


def _upsert_report(db, market: str, report_date: date) -> Report:
    stmt = select(Report).where(Report.market == market, Report.report_date == report_date)
    existing = db.execute(stmt).scalar_one_or_none()
    if existing is not None:
        existing.sectors.clear()
        existing.movers.clear()
        return existing
    new = Report(market=market, report_date=report_date)
    db.add(new)
    return new


def _persist(
    market: str,
    report_date: date,
    *,
    summary_md: str,
    sources,
    model_id: str,
    sectors: list[MarketSector],
    movers: list[MarketMover],
    indices: list[dict] | None = None,
    themes: list[dict] | None = None,
) -> int:
    with SessionLocal() as db:
        report = _upsert_report(db, market, report_date)
        report.summary_md = summary_md
        report.raw_sources = sources
        report.indices = indices or []
        report.themes = themes or []
        report.generated_at = datetime.now(timezone.utc)
        report.model_used = model_id
        report.status = "ok"

        db.flush()
        for s in sectors:
            s.report_id = report.id
            db.add(s)
        for m in movers:
            m.report_id = report.id
            db.add(m)
        db.commit()
        log.info(
            "pipeline ok market=%s date=%s report_id=%s sectors=%d movers=%d",
            market,
            report_date,
            report.id,
            len(sectors),
            len(movers),
        )
        return report.id


def _persist_failed(market: str, report_date: date, reason: str, sources) -> int:
    with SessionLocal() as db:
        report = _upsert_report(db, market, report_date)
        report.summary_md = f"数据获取失败：{reason}"
        report.raw_sources = sources
        report.generated_at = datetime.now(timezone.utc)
        report.model_used = ""
        report.status = "failed"
        db.commit()
        return report.id
