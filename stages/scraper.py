"""Stage A: Scraper — Apify TikTok top videos for a creator."""
import os
import logging
from typing import Callable

from apify_client import ApifyClient

logger = logging.getLogger(__name__)

APIFY_API_KEY = os.getenv("APIFY_API_KEY", "")
ACTOR_ID = os.getenv("APIFY_ACTOR_ID", "z6GDWcyb4ZVT10ogS")


async def run(job: dict, emit: Callable) -> None:
    handle = job["handle"]
    emit("progress", {"stage": "A", "message": f"Fetching @{handle}'s TikTok videos via Apify..."})

    if not APIFY_API_KEY:
        raise RuntimeError("APIFY_API_KEY environment variable not set")

    client = ApifyClient(APIFY_API_KEY)
    run_input = {
        "usernames": [handle],
        "maxItems": 30,
        "getTranscripts": True,
    }

    logger.info("Starting Apify actor %s for @%s", ACTOR_ID, handle)
    emit("progress", {"stage": "A", "message": f"Apify scraping @{handle} — this takes ~60s..."})

    try:
        actor_run = client.actor(ACTOR_ID).call(run_input=run_input, max_items=30)
    except Exception as e:
        logger.error("Apify actor call failed: %s", e, exc_info=True)
        raise RuntimeError(f"Apify scraper failed: {e}") from e

    dataset_id = actor_run.get("defaultDatasetId")
    if not dataset_id:
        raise RuntimeError("Apify returned no dataset ID")

    items = list(client.dataset(dataset_id).iterate_items())
    logger.info("Apify returned %d items for @%s", len(items), handle)

    if not items:
        raise RuntimeError(f"Apify returned 0 videos for @{handle}. Check the handle is correct.")

    def get_views(v):
        return v.get("playCount") or v.get("stats", {}).get("playCount") or 0

    videos = sorted(items, key=get_views, reverse=True)[:10]

    job["videos"] = []
    for v in videos:
        stats = v.get("stats", {})
        video_id = str(v.get("id") or v.get("videoId") or "")
        url = v.get("webVideoUrl") or v.get("url") or v.get("shareUrl") or ""
        download_url = v.get("videoUrl") or v.get("downloadUrl") or url

        job["videos"].append({
            "video_id": video_id,
            "url": url,
            "download_url": download_url,
            "views": get_views(v),
            "likes": v.get("diggCount") or stats.get("diggCount") or 0,
            "comments": v.get("commentCount") or stats.get("commentCount") or 0,
            "shares": v.get("shareCount") or stats.get("shareCount") or 0,
            "duration": v.get("videoMeta", {}).get("duration") or v.get("duration") or 0,
            "description": v.get("text") or v.get("desc") or "",
            "created_at": v.get("createTimeISO") or v.get("createTime") or "",
            "cover_url": (v.get("covers") or {}).get("default") or v.get("coverUrl") or "",
            "transcript": v.get("transcript") or "",
        })

    emit("progress", {
        "stage": "A",
        "message": f"Found {len(job['videos'])} top videos for @{handle}",
        "done": True,
        "count": len(job["videos"]),
    })
    logger.info("Stage A complete: %d videos for @%s", len(job["videos"]), handle)
