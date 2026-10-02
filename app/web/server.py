from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.insights.collector import collect_reel_insights
from app.logger import logger

from .service import (
    get_dashboard_summary,
    get_reel,
    get_reels,
    health_check,
)

app = FastAPI(
    title="Instagram Automation",
    version="1.0.0",
    docs_url="/docs",
    redoc_url=None,
)

app.mount(
    "/static",
    StaticFiles(directory="app/web/static"),
    name="static",
)


@app.get("/", include_in_schema=False)
def dashboard():
    return FileResponse("app/web/templates/index.html")


@app.get("/api/health")
def api_health():
    return health_check()


@app.get("/api/dashboard")
def api_dashboard():
    return get_dashboard_summary()


@app.get("/api/reels")
def api_reels():
    return {"reels": get_reels()}


@app.get("/api/reels/{media_id}")
def api_reel(media_id: str):
    reel = get_reel(media_id)

    if reel is None:
        raise HTTPException(status_code=404, detail="Reel not found")

    return reel


@app.post("/api/insights/collect")
def api_collect_insights(media_id: str | None = None):
    logger.info(
        "Web insights collection requested media_id=%s",
        media_id,
    )

    data = collect_reel_insights(media_id)

    return {
        "status": "ok",
        "last_updated": data.get("last_updated"),
        "reels": len(data.get("reels", {})),
    }
