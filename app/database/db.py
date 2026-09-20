import sqlite3
import json
import logging
from pathlib import Path
from typing import Any

from app.core.config import DB_PATH

logger = logging.getLogger(__name__)

CREATE_VIDEOS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    theme TEXT NOT NULL,
    narration TEXT NOT NULL,
    caption TEXT NOT NULL,
    video_path TEXT,
    status TEXT NOT NULL CHECK (status IN ('DRAFT', 'READY_FOR_REVIEW', 'APPROVED', 'REJECTED', 'PUBLISHED')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_SOCIAL_AUTH_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS social_auth (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL,
    account_name TEXT,
    open_id TEXT UNIQUE,
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_TRENDS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS trends (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tag TEXT NOT NULL,
    title TEXT NOT NULL,
    engagement_score REAL NOT NULL,
    url TEXT,
    raw_data TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def get_connection(db_file: Path | str | None = None) -> sqlite3.Connection:
    """Get a connection to the SQLite database with row factory enabled."""
    target_path = Path(db_file or DB_PATH).resolve()
    target_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(target_path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_file: Path | str | None = None) -> None:
    """Initialize database tables."""
    with get_connection(db_file) as conn:
        conn.execute(CREATE_VIDEOS_TABLE_SQL)
        conn.execute(CREATE_TRENDS_TABLE_SQL)
        conn.execute(CREATE_SOCIAL_AUTH_TABLE_SQL)
        conn.commit()
    logger.info("Database initialized successfully at %s", db_file or DB_PATH)


def insert_video(
    title: str,
    theme: str,
    narration: str,
    caption: str,
    video_path: str | Path | None = None,
    status: str = "DRAFT",
    db_file: Path | str | None = None,
) -> int:
    """Insert a new video record into the database.

    Args:
        title: Title of the video.
        theme: Stoic theme or topic.
        narration: Full text read by TTS.
        caption: TikTok caption and hashtags.
        video_path: Optional path to rendered video file.
        status: Initial lifecycle status. Default 'DRAFT'.
        db_file: Optional database path.

    Returns:
        The generated integer id of the inserted video.
    """
    v_path_str = str(Path(video_path).resolve()) if video_path else None
    query = """
    INSERT INTO videos (title, theme, narration, caption, video_path, status)
    VALUES (?, ?, ?, ?, ?, ?);
    """
    with get_connection(db_file) as conn:
        cursor = conn.cursor()
        cursor.execute(query, (title, theme, narration, caption, v_path_str, status))
        conn.commit()
        video_id = cursor.lastrowid
        logger.info("Inserted video record id=%d [status=%s]", video_id, status)
        return video_id


def update_video_status(
    video_id: int,
    status: str,
    video_path: str | Path | None = None,
    db_file: Path | str | None = None,
) -> bool:
    """Update status and optionally video_path for a video record.

    Args:
        video_id: Target video ID.
        status: New status ('DRAFT', 'READY_FOR_REVIEW', 'APPROVED', 'REJECTED', 'PUBLISHED').
        video_path: Optional updated video file path.
        db_file: Optional database path.

    Returns:
        True if a row was updated, False otherwise.
    """
    valid_statuses = {"DRAFT", "READY_FOR_REVIEW", "APPROVED", "REJECTED", "PUBLISHED"}
    if status not in valid_statuses:
        raise ValueError(f"Invalid status '{status}'. Must be one of: {valid_statuses}")

    if video_path is not None:
        query = "UPDATE videos SET status = ?, video_path = ? WHERE id = ?;"
        params = (status, str(Path(video_path).resolve()), video_id)
    else:
        query = "UPDATE videos SET status = ? WHERE id = ?;"
        params = (status, video_id)

    with get_connection(db_file) as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        updated = cursor.rowcount > 0
        if updated:
            logger.info("Updated video id=%d -> status=%s", video_id, status)
        else:
            logger.warning("No video found with id=%d to update", video_id)
        return updated


def get_video_by_id(video_id: int, db_file: Path | str | None = None) -> dict[str, Any] | None:
    """Retrieve a single video record by its ID.

    Returns:
        Dict representing the video row, or None if not found.
    """
    query = "SELECT * FROM videos WHERE id = ?;"
    with get_connection(db_file) as conn:
        cursor = conn.cursor()
        cursor.execute(query, (video_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_pending_videos(db_file: Path | str | None = None) -> list[dict[str, Any]]:
    """Retrieve all videos waiting for user review ('READY_FOR_REVIEW').

    Returns:
        List of video dicts ordered by creation date descending.
    """
    query = "SELECT * FROM videos WHERE status = 'READY_FOR_REVIEW' ORDER BY created_at DESC;"
    with get_connection(db_file) as conn:
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        return [dict(r) for r in rows]


def get_all_videos(db_file: Path | str | None = None) -> list[dict[str, Any]]:
    """Retrieve all videos in the database.

    Returns:
        List of all video dicts ordered by created_at DESC.
    """
    query = "SELECT * FROM videos ORDER BY created_at DESC;"
    with get_connection(db_file) as conn:
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        return [dict(r) for r in rows]


def save_trends(
    tag: str,
    trends: list[dict[str, Any]],
    db_file: Path | str | None = None,
) -> int:
    """Save extracted trending video metadata to the trends table.

    Args:
        tag: Topic/hashtag searched.
        trends: List of metadata dicts from scraper.
        db_file: Optional database path.

    Returns:
        Number of trend records inserted.
    """
    if not trends:
        return 0

    init_db(db_file)
    clean_tag = tag.strip().lstrip("#")
    query = """
    INSERT INTO trends (tag, title, engagement_score, url, raw_data)
    VALUES (?, ?, ?, ?, ?);
    """

    inserted = 0
    with get_connection(db_file) as conn:
        cursor = conn.cursor()
        for item in trends:
            title = item.get("title", "Sin título")
            eng = float(item.get("engagement_rate", 0.0))
            url = item.get("url", "")
            raw_data = json.dumps(item, ensure_ascii=False)
            cursor.execute(query, (clean_tag, title, eng, url, raw_data))
            inserted += 1
        conn.commit()

    logger.info("Saved %d trending items for tag #%s into trends table", inserted, clean_tag)
    return inserted


def get_top_trends(
    limit: int = 5,
    tag: str | None = None,
    db_file: Path | str | None = None,
) -> list[dict[str, Any]]:
    """Retrieve top trending items ordered by engagement_score descending.

    Args:
        limit: Number of records to return. Default 5.
        tag: Optional filter by tag.
        db_file: Optional database path.

    Returns:
        List of trend dictionaries with parsed raw_data.
    """
    init_db(db_file)

    if tag:
        clean_tag = tag.strip().lstrip("#")
        query = "SELECT * FROM trends WHERE tag = ? ORDER BY engagement_score DESC, created_at DESC LIMIT ?;"
        params = (clean_tag, limit)
    else:
        query = "SELECT * FROM trends ORDER BY engagement_score DESC, created_at DESC LIMIT ?;"
        params = (limit,)

    with get_connection(db_file) as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        results: list[dict[str, Any]] = []
        for r in rows:
            d = dict(r)
            if d.get("raw_data"):
                try:
                    d["metadata"] = json.loads(d["raw_data"])
                except Exception:
                    d["metadata"] = {}
            results.append(d)
        return results


def save_social_token(
    platform: str,
    account_name: str,
    open_id: str,
    access_token: str,
    refresh_token: str | None = None,
    db_file: Path | str | None = None,
) -> int:
    """Insert or replace a social auth token."""
    query = """
    INSERT INTO social_auth (platform, account_name, open_id, access_token, refresh_token, updated_at)
    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    ON CONFLICT(open_id) DO UPDATE SET
        access_token=excluded.access_token,
        refresh_token=excluded.refresh_token,
        updated_at=CURRENT_TIMESTAMP;
    """
    with get_connection(db_file) as conn:
        cursor = conn.cursor()
        cursor.execute(query, (platform, account_name, open_id, access_token, refresh_token))
        conn.commit()
        return cursor.lastrowid or 0


def get_active_token(platform: str = "tiktok", db_file: Path | str | None = None) -> dict[str, Any] | None:
    """Get the first active token for a platform."""
    query = "SELECT * FROM social_auth WHERE platform = ? ORDER BY updated_at DESC LIMIT 1;"
    with get_connection(db_file) as conn:
        cursor = conn.cursor()
        cursor.execute(query, (platform,))
        row = cursor.fetchone()
        return dict(row) if row else None

