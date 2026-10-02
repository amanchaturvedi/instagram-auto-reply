from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.comments import discover, discover_all, process
from app.comments.stats import get_comment_stats, refresh_comment_stats
from app.config import (
    IG_USER_ID,
    MY_USERNAME,
    REPLY_MESSAGE,
    get_reply_config_map,
    get_replyable_media,
    save_reply_config,
)
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

COMMENT_REPLY_SCAN_LIMIT = 10_000

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
        "reply_message": REPLY_MESSAGE,
        "reply_enabled": bool(REPLY_MESSAGE.strip()),
        "reply_keywords": [
            "location",
            "loc",
            "link",
            "map",
            "maps",
            "which place",
            "where",
            "details",
            "📍",
        ],
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


@app.get("/api/comments")
def api_comments():
    return get_comment_stats()


@app.post("/api/comments/refresh")
def api_refresh_comments():
    logger.info("Web comment stats refresh requested")
    return refresh_comment_stats()


def _replyable_media_name(media_id):
    for media_name, media in get_replyable_media().items():
        if media["media_id"] == media_id:
            return media_name

    return None


@app.post("/api/comments/reply/{media_id}")
def api_reply_comments_for_reel(media_id: str):
    if not REPLY_MESSAGE.strip():
        raise HTTPException(
            status_code=400,
            detail="Set REPLY_MESSAGE in app/config.py before replying.",
        )

    media_name = _replyable_media_name(media_id)

    if media_name is None:
        raise HTTPException(
            status_code=400,
            detail="This Reel is not enabled for replies. Enable it in Config first.",
        )

    logger.info(
        "Web Reel reply run requested media=%s media_id=%s scan_limit=%d",
        media_name,
        media_id,
        COMMENT_REPLY_SCAN_LIMIT,
        extra={"highlight": "start"},
    )

    discover(media_name, COMMENT_REPLY_SCAN_LIMIT)
    process(media_name)

    return refresh_comment_stats()


@app.post("/api/comments/reply")
def api_reply_comments():
    if not REPLY_MESSAGE.strip():
        raise HTTPException(
            status_code=400,
            detail="Set REPLY_MESSAGE in app/config.py before replying.",
        )

    logger.info(
        "Web Reply All run requested scan_limit=%d",
        COMMENT_REPLY_SCAN_LIMIT,
        extra={"highlight": "start"},
    )

    discover_all(COMMENT_REPLY_SCAN_LIMIT)
    process()

    return refresh_comment_stats()


@app.get("/api/reels/{media_id}")
def api_reel(media_id: str):
    reel = get_reel(media_id)

    if reel is None:
        raise HTTPException(status_code=404, detail="Reel not found")

    return reel
