from .metrics import enrich_reel_metrics


def _percentile(values, fraction):
    values = sorted(float(value) for value in values if value is not None)

    if not values:
        return None

    if len(values) == 1:
        return round(values[0], 3)

    position = (len(values) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(values) - 1)
    weight = position - lower

    return round(
        values[lower] + (values[upper] - values[lower]) * weight,
        3,
    )


def build_account_baseline(reels):
    latest_metrics = []

    for reel in reels:
        snapshots = reel.get("snapshots", [])
        if not snapshots:
            continue

        latest = max(
            snapshots,
            key=lambda snapshot: snapshot.get("collected_at") or "",
        )

        latest_metrics.append(
            enrich_reel_metrics(latest.get("metrics"))
        )

    fields = (
        "views",
        "reach",
        "likes",
        "comments",
        "shares",
        "saved",
        "total_interactions",
        "avg_watch_time_ms",
        "skip_rate",
    )

    baseline = {}

    for field in fields:
        values = [
            metrics.get(field)
            for metrics in latest_metrics
            if metrics.get(field) is not None
        ]

        baseline[field] = {
            "count": len(values),
            "median": _percentile(values, 0.50),
            "p25": _percentile(values, 0.25),
            "p75": _percentile(values, 0.75),
        }

    return {
        "reels_in_baseline": len(latest_metrics),
        "metrics": baseline,
    }
