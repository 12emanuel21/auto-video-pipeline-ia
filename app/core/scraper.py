"""Market Intelligence and Trend Scraping module using yt-dlp."""

import logging
from typing import Any
import yt_dlp

logger = logging.getLogger(__name__)


def extract_trending_metadata(
    tag: str = "estoicismo",
    max_results: int = 10,
) -> list[dict[str, Any]]:
    """Extract public short-form viral video metadata and engagement metrics.

    Args:
        tag: Topic, niche, or hashtag to search (e.g. "estoicismo", "disciplina").
        max_results: Maximum number of video records to retrieve. Default is 10.

    Returns:
        List of dictionaries sorted by engagement_rate descending, containing:
        - id: Video ID
        - title: Clean title or caption
        - description: Full description / copy
        - view_count: Total views
        - like_count: Likes
        - comment_count: Comments
        - url: Direct public URL
        - duration: Video duration in seconds
        - engagement_rate: Percentage ((likes + comments) / views) * 100
    """
    clean_tag = tag.strip().lstrip("#")
    logger.info("Extracting trending metadata for tag: #%s (max_results=%d)", clean_tag, max_results)

    # Search query targeting vertical shorts and viral videos in the niche
    query = f"ytsearch{max_results}:{clean_tag} shorts viral reflexiones"

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "ignoreerrors": True,
        "extract_flat": False,
        "skip_download": True,
    }

    results: list[dict[str, Any]] = []

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            extracted = ydl.extract_info(query, download=False)
            if not extracted:
                logger.warning("No metadata returned by yt-dlp for query: %s", query)
                return []

            entries = extracted.get("entries") or [extracted]

            for item in entries:
                if not item:
                    continue

                item_id = str(item.get("id", ""))
                title = str(item.get("title", "")).strip()
                description = str(item.get("description", "")).strip() or title
                view_count = int(item.get("view_count") or 0)
                like_count = int(item.get("like_count") or 0)
                comment_count = int(item.get("comment_count") or 0)
                duration = float(item.get("duration") or 0.0)

                # Resolve public web URL
                webpage_url = (
                    item.get("webpage_url")
                    or item.get("url")
                    or f"https://www.youtube.com/watch?v={item_id}"
                )

                # Calculate engagement rate: ((likes + comments) / views) * 100
                denom = max(view_count, 1)
                engagement_rate = round(((like_count + comment_count) / denom) * 100, 2)

                results.append(
                    {
                        "id": item_id,
                        "title": title,
                        "description": description,
                        "view_count": view_count,
                        "like_count": like_count,
                        "comment_count": comment_count,
                        "url": webpage_url,
                        "duration": duration,
                        "engagement_rate": engagement_rate,
                    }
                )

    except Exception as exc:
        logger.error("Error scraping metadata for tag '%s': %s", clean_tag, exc)

    # Sort entries by engagement_rate descending
    results.sort(key=lambda x: x["engagement_rate"], reverse=True)
    logger.info("Successfully extracted and ranked %d trending videos for #%s", len(results), clean_tag)
    return results
