from .baseline import build_account_baseline
from .metrics import enrich_reel_metrics
from .posting_time import build_posting_time_analysis, posting_features, select_snapshot_at_age


def _latest_snapshot(reel):
    snapshots = reel.get("snapshots", [])
    if not snapshots:
        return None

    return max(
        snapshots,
        key=lambda snapshot: snapshot.get("collected_at") or "",
    )


def build_reel_analysis_context(reel, target_age_hours=24):
    latest = _latest_snapshot(reel)
    metrics = enrich_reel_metrics(
        latest.get("metrics") if latest else {}
    )

    age_snapshot = select_snapshot_at_age(
        reel,
        target_age_hours=target_age_hours,
    )

    return {
        "media_id": reel.get("media_id"),
        "caption": reel.get("caption"),
        "timestamp": reel.get("timestamp"),
        "posting": posting_features(reel.get("timestamp")),
        "latest": {
            "collected_at": latest.get("collected_at") if latest else None,
            "metrics": metrics,
        },
        "age_normalized": {
            "target_age_hours": target_age_hours,
            "snapshot": age_snapshot,
        },
    }


def build_account_analysis_context(reels, target_age_hours=24):
    baseline = build_account_baseline(reels)

    return {
        "generated_from_reels": len(reels),
        "baseline": baseline,
        "posting_time": build_posting_time_analysis(
            reels,
            target_age_hours=target_age_hours,
        ),
        "reels": [
            build_reel_analysis_context(
                reel,
                target_age_hours=target_age_hours,
            )
            for reel in reels
        ],
    }
