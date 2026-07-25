import sqlite3
from logger import logger

DB_NAME = "instagram.db"

conn = sqlite3.connect(DB_NAME)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# ----------------------------
# Schema
# ----------------------------

cursor.execute("""
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
)
""")

conn.commit()


# ----------------------------
# Queue
# ----------------------------

def enqueue(comment, media_name, media_id):
    """
    Add comment to processing queue.
    Duplicate comment_ids are ignored.
    """

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
        comment.get("timestamp"),
        media_name,
        media_id
    ))

    conn.commit()
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
        logger.debug("Skipped duplicate queue entry comment_id=%s", comment.get("id"))

    return inserted


def get_pending_comments(media_name: str, limit=None):
    query = """
        SELECT *
        FROM queue
        WHERE status IN ('PENDING', 'DM_SENT', 'FAILED') AND media_name = ?
        ORDER BY timestamp ASC
    """

    params = [media_name]

    if limit is not None:
        query += " LIMIT ?"
        params.append(limit)

    cursor.execute(query, params)
    return cursor.fetchall()


def mark_dm_sent(comment_id):

    cursor.execute("""
        UPDATE queue
        SET status='DM_SENT'
        WHERE comment_id=?
    """, (comment_id,))

    conn.commit()
    logger.info("Marked DM sent comment_id=%s rows_updated=%d", comment_id, cursor.rowcount)


def mark_done(comment_id):

    cursor.execute("""
        UPDATE queue
        SET status='DONE'
        WHERE comment_id=?
    """, (comment_id,))

    conn.commit()
    logger.info("Marked comment done comment_id=%s rows_updated=%d", comment_id, cursor.rowcount)


def mark_failed(comment_id):

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

    conn.commit()
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

    cursor.execute("""
        SELECT COUNT(*)
        FROM queue
        WHERE status=?
    """, (status,))

    size = cursor.fetchone()[0]
    logger.debug("Queue size status=%s count=%d", status, size)
    return size


def clear_done():

    cursor.execute("""
        SELECT
            comment_id,
            username,
            comment,
            timestamp,
            retries,
            created_at
        FROM queue
        WHERE status='DONE'
        ORDER BY timestamp ASC
    """)
    rows = cursor.fetchall()

    for row in rows:
        comment = " ".join((row["comment"] or "").split())
        if len(comment) > 120:
            comment = f"{comment[:117]}..."

        logger.info(
            "Deleting completed queue entry comment_id=%s username=%s retries=%s timestamp=%s created_at=%s comment=%r",
            row["comment_id"],
            row["username"],
            row["retries"],
            row["timestamp"],
            row["created_at"],
            comment,
        )

    cursor.execute("""
        DELETE
        FROM queue
        WHERE status='DONE'
    """)

    conn.commit()
    logger.info("Cleared done queue entries rows_deleted=%d", cursor.rowcount)


def reset_failed():

    cursor.execute("""
        UPDATE queue
        SET
            status='PENDING',
            retries=0
        WHERE status='FAILED'
    """)

    conn.commit()
    logger.info("Reset failed queue entries rows_updated=%d", cursor.rowcount)
