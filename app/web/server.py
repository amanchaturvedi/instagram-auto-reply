from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.analytics import (
    build_account_analysis_context,
    build_account_evidence,
    build_reel_analysis_for_media,
)
from app.comments import discover, discover_all, process
from app.config import (
    IG_USER_ID,
    MY_USERNAME,
    get_reply_config_map,
    get_replyable_media,
    save_reply_config,
)
from app.database import get_pending_count_by_media
from ai.analyzers import AccountAnalyzer, ReelAnalyzer
from app.insights.catalog import refresh_reel_catalog
from app.insights.collector import collect_reel_insights
from app.logger import logger

from .service import (
    get_dashboard_summary,
    get_reel,
    get_reels,
    health_check,
)

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
INDEX_FILE = BASE_DIR / "templates" / "index.html"

COMMENT_REPLY_SCAN_LIMIT = 100
COMMENT_REPLY_MAX_SCAN_LIMIT = 500

app = FastAPI(
    title="Instagram Automation",
    version="1.0.0",
    docs_url="/docs",
    redoc_url=None,
)

app.mount(
    "/static",
    StaticFiles(directory=STATIC_DIR),
    name="static",
)


def _config_reels():
    config_map = get_reply_config_map()
    catalog = {
        reel["media_id"]: reel
        for reel in get_reels()
        if reel.get("media_id")
    }

    rows = []

    for media_id, reel in catalog.items():
        entry = config_map.get(media_id, {})

        rows.append(
            {
                "media_id": media_id,
                "media_name": entry.get("media_name") or f"reel_{media_id}",
                "caption": reel.get("caption"),
                "timestamp": reel.get("timestamp"),
                "enabled": bool(entry.get("enabled", False)),
                "location": entry.get("location", ""),
            }
        )

    for media_id, entry in config_map.items():
        if media_id in catalog:
            continue

        rows.append(
            {
                "media_id": media_id,
                "media_name": entry.get("media_name") or f"reel_{media_id}",
                "caption": None,
                "timestamp": None,
                "enabled": bool(entry.get("enabled", False)),
                "location": entry.get("location", ""),
            }
        )

    rows.sort(
        key=lambda reel: reel.get("timestamp") or "",
        reverse=True,
    )

    return rows


@app.get("/", include_in_schema=False)
def dashboard():
    return FileResponse(INDEX_FILE)


@app.get("/api/health")
def api_health():
    return health_check()


@app.get("/api/config")
def api_config():
    return {
        "instagram_user_id": IG_USER_ID,
        "username": MY_USERNAME,
        "timezone": "Asia/Kolkata",
        "reels": _config_reels(),
    }


@app.post("/api/config")
def api_save_config(payload: dict):
    reels = payload.get("reels")

    if not isinstance(reels, list):
        raise HTTPException(
            status_code=400,
            detail="reels must be an array",
        )

    try:
        save_reply_config(reels)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    logger.info(
        "Reply configuration updated entries=%d",
        len(reels),
        extra={"highlight": "summary"},
    )

    return api_config()


@app.get("/api/dashboard")
def api_dashboard():
    return get_dashboard_summary()


@app.get("/api/analytics")
def api_analytics():
    return build_account_analysis_context()


@app.get("/api/analytics/posting-time")
def api_analytics_posting_time():
    return build_account_analysis_context()["posting_time"]


@app.get("/api/analytics/reels/{media_id}")
def api_analytics_reel(media_id: str):
    analysis = build_reel_analysis_for_media(media_id)

    if analysis is None:
        raise HTTPException(status_code=404, detail="Reel not found")

    return analysis


@app.post("/api/ai/account")
def api_ai_account():
    try:
        evidence = build_account_evidence()
        analysis = AccountAnalyzer().analyze(evidence)
        return {
            "status": "ok",
            "reels_analyzed": evidence["dataset"]["reels_analyzed"],
            "reels_with_24h_snapshot": evidence["dataset"]["reels_with_24h_snapshot"],
            "analysis_metric_source": evidence["dataset"]["analysis_metric_source"],
            "analysis": analysis,
        }
    except Exception as exc:
        logger.exception("AI account analysis failed")
        raise HTTPException(status_code=502, detail=f"AI analysis failed: {exc}") from exc


@app.post("/api/ai/reels/{media_id}")
def api_ai_reel(media_id: str):
    context = build_reel_analysis_for_media(media_id)
    if context is None:
        raise HTTPException(status_code=404, detail="Reel not found")
    try:
        return {"status": "ok", "media_id": media_id, "analysis": ReelAnalyzer().analyze(context)}
    except Exception as exc:
        logger.exception("AI Reel analysis failed media_id=%s", media_id)
        raise HTTPException(status_code=502, detail=f"AI analysis failed: {exc}") from exc


@app.get("/api/reels")
def api_reels():
    return {"reels": get_reels()}


@app.post("/api/reels/refresh")
def api_refresh_reels():
    logger.info("Web Reel catalog refresh requested")
    return refresh_reel_catalog()


@app.post("/api/reels/{media_id}/refresh")
def api_refresh_reel(media_id: str):
    logger.info(
        "Web Reel insights refresh requested media_id=%s",
        media_id,
    )

    data = collect_reel_insights(media_id)

    return {
        "status": "ok",
        "media_id": media_id,
        "last_updated": data.get("last_updated"),
    }


def _comment_dashboard():
    replyable_media = get_replyable_media()
    media_ids = [media["media_id"] for media in replyable_media.values()]
    pending_counts = get_pending_count_by_media(media_ids)

    reels_by_id = {
        reel["media_id"]: reel
        for reel in get_reels()
        if reel.get("media_id")
    }

    reels = {}

    for media_name, media in replyable_media.items():
        media_id = media["media_id"]
        catalog_reel = reels_by_id.get(media_id, {})

        reels[media_name] = {
            "media_name": media_name,
            "media_id": media_id,
            "caption": catalog_reel.get("caption"),
            "timestamp": catalog_reel.get("timestamp"),
            "pending_comments": int(pending_counts.get(media_id, 0)),
        }

    return {
        "status": "ok",
        "last_updated": None,
        "reels": reels,
    }


@app.get("/api/comments")
def api_comments():
    return _comment_dashboard()


def _validate_comment_limit(limit):
    if limit < 1 or limit > COMMENT_REPLY_MAX_SCAN_LIMIT:
        raise HTTPException(
            status_code=400,
            detail=f"limit must be between 1 and {COMMENT_REPLY_MAX_SCAN_LIMIT}",
        )
    return limit


@app.post("/api/comments/refresh")
def api_refresh_comments(limit: int = COMMENT_REPLY_SCAN_LIMIT):
    _validate_comment_limit(limit)

    logger.info(
        "Web comment discovery requested; maps to discover_all scan_limit=%d",
        limit,
    )

    discover_all(limit)
    return _comment_dashboard()


@app.post("/api/comments/refresh/{media_id}")
def api_refresh_comments_for_reel(
    media_id: str,
    limit: int = COMMENT_REPLY_SCAN_LIMIT,
):
    _validate_comment_limit(limit)

    media_name = _replyable_media_name(media_id)

    if media_name is None:
        raise HTTPException(
            status_code=400,
            detail="This Reel is not enabled for replies. Enable it in Config first.",
        )

    logger.info(
        "Web Reel comment discovery requested media=%s media_id=%s scan_limit=%d",
        media_name,
        media_id,
        limit,
    )

    discover(media_name, limit)
    return _comment_dashboard()


def _replyable_media_name(media_id):
    for media_name, media in get_replyable_media().items():
        if media["media_id"] == media_id:
            return media_name

    return None


@app.post("/api/comments/reply/{media_id}")
def api_reply_comments_for_reel(media_id: str):
    media_name = _replyable_media_name(media_id)

    if media_name is None:
        raise HTTPException(
            status_code=400,
            detail="This Reel is not enabled for replies. Enable it in Config first.",
        )

    logger.info(
        "Web Reel process requested media=%s media_id=%s",
        media_name,
        media_id,
        extra={"highlight": "start"},
    )

    result = process(media_name)

    return {
        "status": "ok",
        "processing": result,
        "comments": _comment_dashboard(),
    }


@app.post("/api/comments/reply")
def api_reply_comments():
    logger.info(
        "Web Reply All process requested",
        extra={"highlight": "start"},
    )

    result = process()

    return {
        "status": "ok",
        "processing": result,
        "comments": _comment_dashboard(),
    }


@app.get("/api/reels/{media_id}")
def api_reel(media_id: str):
    reel = get_reel(media_id)

    if reel is None:
        raise HTTPException(status_code=404, detail="Reel not found")

    return reel
