from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.comments.service import get_comments
from app.insights.catalog import refresh_reel_catalog
from app.insights.collector import collect_reel_insights
from app.logger import logger

from .service import (
    get_dashboard_summary,
    get_reel,
    get_reels,
    health_check,
)

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
INDEX_FILE = BASE_DIR / "templates" / "index.html"

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


@app.get("/", include_in_schema=False)
def dashboard():
    return FileResponse(INDEX_FILE)


@app.get("/api/health")
def api_health():
    return health_check()


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


@app.get("/api/reels/{media_id}")
def api_reel(media_id: str):
    reel = get_reel(media_id)

    if reel is None:
        raise HTTPException(status_code=404, detail="Reel not found")

    return reel


@app.get("/api/reels/{media_id}/comments")
def api_reel_comments(media_id: str, limit: int = 20):
    if limit < 1 or limit > 100:
        raise HTTPException(
            status_code=400,
            detail="limit must be between 1 and 100",
        )

    comments = []

    for comment in get_comments(media_id, limit):
        comments.append(
            {
                "id": comment.get("id"),
                "username": comment.get("from", {}).get("username"),
                "text": comment.get("text"),
                "timestamp": comment.get("timestamp"),
                "parent_id": comment.get("parent_id"),
                "hidden": comment.get("hidden", False),
            }
        )

    return {"comments": comments}


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
