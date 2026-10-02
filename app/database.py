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

    FastAPI runs synchronous route handlers in worker threads, so a single
    module-level SQLite connection is not safe to share across requests.
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
                media_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'PENDING',
                retries INTEGER NOT NULL DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_queue_media_status
            ON queue(media_id, status);

            CREATE TABLE IF NOT EXISTS reply_config(
                media_id TEXT PRIMARY KEY,
                media_name TEXT NOT NULL,
                location TEXT NOT NULL DEFAULT '',
                enabled INTEGER NOT NULL DEFAULT 0,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)

        schema_version = connection.execute(
            "PRAGMA user_version"
        ).fetchone()[0]

        if schema_version < 2:
            connection.executescript("""
                DROP TABLE IF EXISTS comment_media_stats;
                DROP TABLE IF EXISTS app_state;

                DELETE FROM queue
                WHERE status = 'DONE';

                UPDATE queue
                SET status = 'PENDING'
                WHERE status = 'FAILED';
            """)

            connection.execute("PRAGMA user_version = 2")

        connection.commit()

        _thread_state.connection = connection
        _thread_state.cursor = connection.cursor()

    return _thread_state.connection, _thread_state.cursor


# ----------------------------
# Reply configuration
# ----------------------------

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

    connection.commit()

    logger.info(
        "Seeded reply configuration defaults rows=%d",
        len(rows),
    )


def replace_reply_config(entries):
    connection, cursor = _get_db()

    rows = [
        (
            str(entry["media_id"]),
            str(entry["media_name"]),
            str(entry.get("location") or ""),
            1 if entry.get("enabled") else 0,
        )
        for entry in entries
    ]

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

        connection.commit()
    except Exception:
        connection.rollback()
        raise

    logger.info(
        "Replaced reply configuration rows=%d",
        len(rows),
        extra={"highlight": "summary"},
    )

# ----------------------------
# Pending comment queue
# ----------------------------

def enqueue(comment, media_name, media_id):
    """
    Add a comment to the pending queue.

    The Instagram comment ID is the idempotency key. Once processing succeeds,
    the row is deleted instead of being retained as reply history.
    """

    connection, cursor = _get_db()

    cursor.execute(
        """
        INSERT OR IGNORE INTO queue(
            comment_id,
            username,
            comment,
            timestamp,
            media_name,
            media_id
        )
        VALUES(?,?,?,?,?,?)
        """,
        (
            comment["id"],
            comment.get("from", {}).get("username"),
            comment.get("text"),
            utc_to_ist(comment.get("timestamp")),
            media_name,
            media_id,
        ),
    )

    connection.commit()
    inserted = cursor.rowcount > 0

    if inserted:
        logger.info(
            "Enqueued pending comment_id=%s username=%s timestamp=%s media_name=%s media_id=%s",
            comment.get("id"),
            comment.get("from", {}).get("username"),
            comment.get("timestamp"),
            media_name,
            media_id,
        )
    else:
        logger.debug(
            "Skipped duplicate pending comment_id=%s",
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


def get_pending_count_by_media(media_ids):
    connection, cursor = _get_db()

    if not media_ids:
        return {}

    placeholders = ",".join("?" for _ in media_ids)

    cursor.execute(
        f"""
        SELECT media_id, COUNT(*) AS pending_comments
        FROM queue
        WHERE media_id IN ({placeholders})
          AND status IN ('PENDING', 'DM_SENT', 'FAILED')
        GROUP BY media_id
        """,
        list(media_ids),
    )

    return {
        row["media_id"]: int(row["pending_comments"])
        for row in cursor.fetchall()
    }


def mark_dm_sent(comment_id):
    connection, cursor = _get_db()

    cursor.execute(
        """
        UPDATE queue
        SET status='DM_SENT'
        WHERE comment_id=?
        """,
        (comment_id,),
    )

    connection.commit()

    logger.info(
        "Marked DM sent comment_id=%s rows_updated=%d",
        comment_id,
        cursor.rowcount,
    )


def remove_processed(comment_id):
    connection, cursor = _get_db()

    cursor.execute(
        """
        DELETE FROM queue
        WHERE comment_id=?
        """,
        (comment_id,),
    )

    connection.commit()

    logger.info(
        "Removed processed comment from pending queue comment_id=%s rows_deleted=%d",
        comment_id,
        cursor.rowcount,
    )


def mark_failed(comment_id):
    connection, cursor = _get_db()

    cursor.execute(
        """
        UPDATE queue
        SET retries = retries + 1
        WHERE comment_id=?
        """,
        (comment_id,),
    )

    connection.commit()

    cursor.execute(
        """
        SELECT status, retries
        FROM queue
        WHERE comment_id=?
        """,
        (comment_id,),
    )

    row = cursor.fetchone()

    logger.warning(
        "Marked comment failed/retry comment_id=%s status=%s retries=%s",
        comment_id,
        row["status"] if row else None,
        row["retries"] if row else None,
    )


def queue_size(status="PENDING"):
    connection, cursor = _get_db()

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM queue
        WHERE status=?
        """,
        (status,),
    )

    size = cursor.fetchone()[0]

    logger.debug(
        "Queue size status=%s count=%d",
        status,
        size,
    )

    return size


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
