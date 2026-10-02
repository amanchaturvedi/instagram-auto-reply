import sqlite3
import threading
from datetime import datetime
from zoneinfo import ZoneInfo

from .logger import logger

DB_NAME = "instagram.db"
DB_TIMEOUT_SECONDS = 30

_thread_state = threading.local()


def _get_db():
    """
    Return a SQLite connection/cursor scoped to the current thread.

    FastAPI runs synchronous route handlers in worker threads. A single
    module-level SQLite connection created during import is therefore not safe
    to reuse from those request threads.
    """

    if not hasattr(_thread_state, "connection"):
        connection = sqlite3.connect(
            DB_NAME,
            timeout=DB_TIMEOUT_SECONDS,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 30000")

        connection.executescript("""
            CREATE TABLE IF NOT EXISTS queue(
                comment_id TEXT PRIMARY KEY,
                username TEXT,
                comment TEXT,
                timestamp TEXT,
                media_name TEXT NOT NULL,
                media_id   TEXT NOT NULL,
                status TEXT DEFAULT 'PENDING',
                retries INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_queue_media_status
            ON queue(media_id, status);

            CREATE TABLE IF NOT EXISTS comment_media_stats(
                media_id TEXT PRIMARY KEY,
                media_name TEXT NOT NULL,
                caption TEXT,
                timestamp TEXT,
                total_comments INTEGER NOT NULL DEFAULT 0,
                discovered_comments INTEGER NOT NULL DEFAULT 0,
                scanned_comments INTEGER NOT NULL DEFAULT 0,
                last_updated TEXT
            );

            CREATE TABLE IF NOT EXISTS reply_config(
                media_id TEXT PRIMARY KEY,
                media_name TEXT NOT NULL,
                location TEXT NOT NULL DEFAULT '',
                enabled INTEGER NOT NULL DEFAULT 0,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS app_state(
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
        """)
        connection.commit()

        _thread_state.connection = connection
        _thread_state.cursor = connection.cursor()

    return _thread_state.connection, _thread_state.cursor


# ----------------------------
# Reply configuration
# ----------------------------

def is_reply_config_initialized():
    connection, cursor = _get_db()

    cursor.execute(
        """
        SELECT value
        FROM app_state
        WHERE key='reply_config_initialized'
        """
    )

    row = cursor.fetchone()
    return bool(row and row["value"] == "1")


def mark_reply_config_initialized():
    connection, cursor = _get_db()

    cursor.execute(
        """
        INSERT INTO app_state(key, value)
        VALUES('reply_config_initialized', '1')
        ON CONFLICT(key) DO UPDATE SET value='1'
        """
    )

    connection.commit()


def seed_reply_config(defaults):
    connection, cursor = _get_db()

    rows = [
        (
            media["media_id"],
            media_name,
            media["location"],
            1,
        )
        for media_name, media in defaults.items()
    ]

    if rows:
        cursor.executemany(
            """
            INSERT OR IGNORE INTO reply_config(
                media_id,
                media_name,
                location,
                enabled
            )
            VALUES(?,?,?,?)
            """,
            rows,
        )

    mark_reply_config_initialized()

    logger.info(
        "Seeded reply configuration defaults rows_inserted=%d",
        cursor.rowcount if rows else 0,
    )


def replace_reply_config(entries):
    connection, cursor = _get_db()

    rows = []
    for entry in entries:
        rows.append(
            (
                str(entry["media_id"]),
                str(entry["media_name"]),
                str(entry.get("location") or ""),
                1 if entry.get("enabled") else 0,
            )
        )

    try:
        cursor.execute("BEGIN")

        cursor.execute("DELETE FROM reply_config")

        if rows:
            cursor.executemany(
                """
                INSERT INTO reply_config(
                    media_id,
                    media_name,
                    location,
                    enabled
                )
                VALUES(?,?,?,?)
                """,
                rows,
            )

        cursor.execute(
            """
            INSERT INTO app_state(key, value)
            VALUES('reply_config_initialized', '1')
            ON CONFLICT(key) DO UPDATE SET value='1'
            """
        )

        connection.commit()
    except Exception:
        connection.rollback()
        raise

    logger.info(
        "Replaced reply configuration rows=%d",
        len(rows),
        extra={"highlight": "summary"},
    )


def get_reply_config_map():
    connection, cursor = _get_db()

    cursor.execute(
        """
        SELECT media_id, media_name, location, enabled
        FROM reply_config
        ORDER BY media_name
        """
    )

    return {
        row["media_id"]: {
            "media_name": row["media_name"],
            "location": row["location"],
            "enabled": bool(row["enabled"]),
        }
        for row in cursor.fetchall()
    }


# ----------------------------
# Comment stats
# ----------------------------

def upsert_comment_media_stats(
    media_name,
    media_id,
    caption,
    timestamp,
    total_comments,
    discovered_comments,
    scanned_comments,
    last_updated,
):
    connection, cursor = _get_db()

    cursor.execute(
        """
        INSERT INTO comment_media_stats(
            media_id,
            media_name,
            caption,
            timestamp,
            total_comments,
            discovered_comments,
            scanned_comments,
            last_updated
        )
        VALUES(?,?,?,?,?,?,?,?)
        ON CONFLICT(media_id) DO UPDATE SET
            media_name=excluded.media_name,
            caption=excluded.caption,
            timestamp=excluded.timestamp,
            total_comments=excluded.total_comments,
            discovered_comments=excluded.discovered_comments,
            scanned_comments=excluded.scanned_comments,
            last_updated=excluded.last_updated
        """,
        (
            media_id,
            media_name,
            caption,
            timestamp,
            int(total_comments),
            int(discovered_comments),
            int(scanned_comments),
            last_updated,
        ),
    )

    connection.commit()


def get_comment_dashboard(replyable_media):
    connection, cursor = _get_db()

    media_ids = [
        media["media_id"]
        for media in replyable_media.values()
    ]

    stats_by_media = {}
    if media_ids:
        placeholders = ",".join("?" for _ in media_ids)

        cursor.execute(
            f"""
            SELECT *
            FROM comment_media_stats
            WHERE media_id IN ({placeholders})
            """,
            media_ids,
        )

        stats_by_media = {
            row["media_id"]: row
            for row in cursor.fetchall()
        }

    queue_counts = {}
    if media_ids:
        placeholders = ",".join("?" for _ in media_ids)

        cursor.execute(
            f"""
            SELECT
                media_id,
                SUM(CASE WHEN status='DONE' THEN 1 ELSE 0 END) AS replied_comments,
                SUM(CASE WHEN status IN ('PENDING', 'DM_SENT', 'FAILED') THEN 1 ELSE 0 END) AS pending_comments
            FROM queue
            WHERE media_id IN ({placeholders})
            GROUP BY media_id
            """,
            media_ids,
        )

        queue_counts = {
            row["media_id"]: row
            for row in cursor.fetchall()
        }

    reels = {}

    for media_name, media in replyable_media.items():
        media_id = media["media_id"]
        stats = stats_by_media.get(media_id)
        counts = queue_counts.get(media_id)

        reels[media_name] = {
            "media_name": media_name,
            "media_id": media_id,
            "caption": stats["caption"] if stats else None,
            "timestamp": stats["timestamp"] if stats else None,
            "total_comments": int(stats["total_comments"]) if stats else 0,
            "replied_comments": int(counts["replied_comments"]) if counts and counts["replied_comments"] is not None else 0,
            "pending_comments": int(counts["pending_comments"]) if counts and counts["pending_comments"] is not None else 0,
            "discovered_comments": int(stats["discovered_comments"]) if stats else 0,
            "scanned_comments": int(stats["scanned_comments"]) if stats else 0,
        }

    summary = {
        "total_comments": sum(
            reel["total_comments"]
            for reel in reels.values()
        ),
        "replied_comments": sum(
            reel["replied_comments"]
            for reel in reels.values()
        ),
        "pending_comments": sum(
            reel["pending_comments"]
            for reel in reels.values()
        ),
    }

    cursor.execute(
        """
        SELECT MAX(last_updated) AS last_updated
        FROM comment_media_stats
        """
    )
    row = cursor.fetchone()

    return {
        "status": "ok",
        "last_updated": row["last_updated"] if row else None,
        "summary": summary,
        "reels": reels,
        "discovered_comments": sum(
            reel["discovered_comments"]
            for reel in reels.values()
        ),
        "failed_reels": 0,
    }


# ----------------------------
# Queue
# ----------------------------

def enqueue(comment, media_name, media_id):
    """
    Add comment to processing queue.
    Duplicate comment_ids are ignored.
    """

    connection, cursor = _get_db()

    cursor.execute("""
        INSERT OR IGNORE INTO queue(
            comment_id,
            username,
            comment,
            timestamp,
            media_name,
            media_id
        )
        VALUES(?,?,?,?,?,?)
    """, (
        comment["id"],
        comment.get("from", {}).get("username"),
        comment.get("text"),
        utc_to_ist(comment.get("timestamp")),
        media_name,
        media_id
    ))

    connection.commit()
    inserted = cursor.rowcount > 0

    if inserted:
        logger.info(
            "Enqueued comment_id=%s username=%s timestamp=%s media_name=%s media_id=%s",
            comment.get("id"),
            comment.get("from", {}).get("username"),
            comment.get("timestamp"),
            media_name,
            media_id
        )
    else:
        logger.debug(
            "Skipped duplicate queue entry comment_id=%s",
            comment.get("id"),
        )

    return inserted


def get_pending_comments(media_name=None, limit=None):
    connection, cursor = _get_db()

    query = """
        SELECT *
        FROM queue
        WHERE status IN ('PENDING', 'DM_SENT', 'FAILED')
    """

    params = []

    if media_name:
        query += " AND media_name = ?"
        params.append(media_name)

    query += " ORDER BY timestamp ASC"

    if limit is not None:
        query += " LIMIT ?"
        params.append(limit)

    cursor.execute(query, params)
    return cursor.fetchall()


def mark_dm_sent(comment_id):
    connection, cursor = _get_db()

    cursor.execute("""
        UPDATE queue
        SET status='DM_SENT'
        WHERE comment_id=?
    """, (comment_id,))

    connection.commit()
    logger.info(
        "Marked DM sent comment_id=%s rows_updated=%d",
        comment_id,
        cursor.rowcount,
    )


def mark_done(comment_id):
    connection, cursor = _get_db()

    cursor.execute("""
        UPDATE queue
        SET status='DONE'
        WHERE comment_id=?
    """, (comment_id,))

    connection.commit()
    logger.info(
        "Marked comment done comment_id=%s rows_updated=%d",
        comment_id,
        cursor.rowcount,
    )


def mark_failed(comment_id):
    connection, cursor = _get_db()

    cursor.execute("""
        UPDATE queue
        SET
            retries = retries + 1,
            status =
                CASE
                    WHEN retries + 1 >= 3
                    THEN 'FAILED'
                    WHEN status = 'DM_SENT'
                    THEN 'DM_SENT'
                    ELSE 'PENDING'
                END
        WHERE comment_id=?
    """, (comment_id,))

    connection.commit()
    rows_updated = cursor.rowcount

    cursor.execute("""
        SELECT status, retries
        FROM queue
        WHERE comment_id=?
    """, (comment_id,))

    row = cursor.fetchone()

    logger.warning(
        "Marked comment failed/retry comment_id=%s status=%s retries=%s rows_updated=%d",
        comment_id,
        row["status"] if row else None,
        row["retries"] if row else None,
        rows_updated,
    )


def queue_size(status="PENDING"):
    connection, cursor = _get_db()

    cursor.execute("""
        SELECT COUNT(*)
        FROM queue
        WHERE status=?
    """, (status,))

    size = cursor.fetchone()[0]

    logger.debug(
        "Queue size status=%s count=%d",
        status,
        size,
    )

    return size


def clear_done():
    """
    Deprecated compatibility hook.

    Completed comments remain in SQLite so reply history and dashboard counts
    are durable instead of being reconstructed from in-memory state.
    """
    logger.debug("Skipping queue cleanup; DONE comments are retained")


def reset_failed():
    connection, cursor = _get_db()

    cursor.execute("""
        UPDATE queue
        SET
            status='PENDING',
            retries=0
        WHERE status='FAILED'
    """)

    connection.commit()

    logger.info(
        "Reset failed queue entries rows_updated=%d",
        cursor.rowcount,
    )


def utc_to_ist(timestamp):
    if not timestamp:
        return None

    dt = datetime.strptime(
        timestamp,
        "%Y-%m-%dT%H:%M:%S%z"
    )

    return dt.astimezone(
        ZoneInfo("Asia/Kolkata")
    ).strftime("%Y-%m-%d %H:%M:%S")
