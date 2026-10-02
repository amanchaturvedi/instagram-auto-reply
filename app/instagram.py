from . import api

REEL_INSIGHT_METRICS = [
    "views",
    "reach",
    "likes",
    "comments",
    "shares",
    "saved",
    "total_interactions",
    "ig_reels_avg_watch_time",
    "ig_reels_video_view_total_time",
    "reels_skip_rate",
]


def get_media(stop_ids=None):
    return api.get_media(stop_ids=stop_ids)


def get_media_by_id(media_id: str):
    return api.get_media_by_id(media_id)


def get_media_insights(media_id: str, metrics=None):
    if metrics is None:
        metrics = REEL_INSIGHT_METRICS

    return api.get_media_insights(media_id, metrics)
