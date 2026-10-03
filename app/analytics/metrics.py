def _number(value):
    return float(value) if value is not None else None


def _rate(numerator, denominator):
    if numerator is None or denominator in (None, 0):
        return None
    return round((float(numerator) / float(denominator)) * 100, 3)


def _growth(current, previous):
    if current is None or previous in (None, 0):
        return None
    return round(((float(current) - float(previous)) / float(previous)) * 100, 3)


def enrich_reel_metrics(metrics):
    metrics = dict(metrics or {})
    reach = _number(metrics.get("reach"))

    metrics["like_rate"] = _rate(metrics.get("likes"), reach)
    metrics["comment_rate"] = _rate(metrics.get("comments"), reach)
    metrics["share_rate"] = _rate(metrics.get("shares"), reach)
    metrics["save_rate"] = _rate(metrics.get("saved"), reach)
    metrics["interaction_rate"] = _rate(metrics.get("total_interactions"), reach)

    return metrics


def compare_metric_snapshots(current, previous):
    current = current or {}
    previous = previous or {}

    keys = (
        "views",
        "reach",
        "likes",
        "comments",
        "shares",
        "saved",
        "total_interactions",
        "avg_watch_time_ms",
        "total_watch_time_ms",
        "skip_rate",
    )

    growth = {}
    for key in keys:
        value = _growth(current.get(key), previous.get(key))
        if value is not None:
            growth[key] = value

    return growth


def enrich_reel_history(reel):
    snapshots = sorted(
        reel.get("snapshots", []),
        key=lambda snapshot: snapshot.get("collected_at") or "",
    )

    enriched = []
    previous_metrics = None

    for snapshot in snapshots:
        metrics = enrich_reel_metrics(snapshot.get("metrics"))
        row = {
            "collected_at": snapshot.get("collected_at"),
            "metrics": metrics,
        }

        if previous_metrics is not None:
            row["growth_vs_previous_snapshot"] = compare_metric_snapshots(
                metrics,
                previous_metrics,
            )

        enriched.append(row)
        previous_metrics = metrics

    return enriched
