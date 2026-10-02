from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
TARGET_AGE_HOURS = 24
MAX_AGE_DEVIATION_HOURS = 8


def parse_datetime(value):
    if not value:
        return None

    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"

    dt = datetime.fromisoformat(text)

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=IST)

    return dt.astimezone(IST)


def posting_features(timestamp):
    dt = parse_datetime(timestamp)
    if dt is None:
        return None

    return {
        "posted_at": dt.isoformat(timespec="seconds"),
        "day_of_week": dt.strftime("%A"),
        "day_of_week_index": dt.weekday(),
        "hour": dt.hour,
        "minute": dt.minute,
        "slot": f"{dt.hour:02d}:00-{(dt.hour + 1) % 24:02d}:00",
        "is_weekend": dt.weekday() >= 5,
    }


def snapshot_age_hours(reel_timestamp, collected_at):
    posted = parse_datetime(reel_timestamp)
    collected = parse_datetime(collected_at)

    if posted is None or collected is None:
        return None

    return round((collected - posted).total_seconds() / 3600, 3)


def select_snapshot_at_age(
    reel,
    target_age_hours=TARGET_AGE_HOURS,
    max_deviation_hours=MAX_AGE_DEVIATION_HOURS,
):
    candidates = []

    for snapshot in reel.get("snapshots", []):
        age = snapshot_age_hours(
            reel.get("timestamp"),
            snapshot.get("collected_at"),
        )

        if age is None:
            continue

        deviation = abs(age - target_age_hours)

        if deviation <= max_deviation_hours:
            candidates.append((deviation, age, snapshot))

    if not candidates:
        return None

    candidates.sort(key=lambda item: (item[0], item[1]))
    deviation, age, snapshot = candidates[0]

    return {
        "snapshot": snapshot,
        "age_hours": age,
        "age_deviation_hours": round(deviation, 3),
    }


def _aggregate(values):
    values = [float(value) for value in values if value is not None]

    if not values:
        return None

    values.sort()

    def percentile(percent):
        if len(values) == 1:
            return values[0]

        position = (len(values) - 1) * percent
        lower = int(position)
        upper = min(lower + 1, len(values) - 1)
        fraction = position - lower
        return values[lower] + (values[upper] - values[lower]) * fraction

    return {
        "count": len(values),
        "median": round(percentile(0.5), 3),
        "p25": round(percentile(0.25), 3),
        "p75": round(percentile(0.75), 3),
    }


def build_posting_time_analysis(reels, target_age_hours=TARGET_AGE_HOURS):
    windows = defaultdict(lambda: defaultdict(list))
    weekdays = defaultdict(lambda: defaultdict(list))
    hours = defaultdict(lambda: defaultdict(list))

    evaluated_reels = 0

    for reel in reels:
        features = posting_features(reel.get("timestamp"))
        selection = select_snapshot_at_age(
            reel,
            target_age_hours=target_age_hours,
        )

        if features is None or selection is None:
            continue

        metrics = selection["snapshot"].get("metrics", {})
        evaluated_reels += 1

        score = {
            "views": metrics.get("views"),
            "reach": metrics.get("reach"),
            "likes": metrics.get("likes"),
            "shares": metrics.get("shares"),
            "saved": metrics.get("saved"),
            "total_interactions": metrics.get("total_interactions"),
        }

        slot = features["slot"]
        weekday = features["day_of_week"]
        hour = str(features["hour"])

        for key, value in score.items():
            windows[slot][key].append(value)
            weekdays[weekday][key].append(value)
            hours[hour][key].append(value)

    def finalize(groups):
        result = {}
        for group, metrics in groups.items():
            result[group] = {
                metric: _aggregate(values)
                for metric, values in metrics.items()
            }
        return result

    return {
        "target_age_hours": target_age_hours,
        "max_age_deviation_hours": MAX_AGE_DEVIATION_HOURS,
        "reels_evaluated": evaluated_reels,
        "by_hour": finalize(hours),
        "by_weekday": finalize(weekdays),
        "by_slot": finalize(windows),
    }
