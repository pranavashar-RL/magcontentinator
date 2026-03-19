"""Stage A: Scraper — Apify TikTok top 10 videos for a creator."""
import os
import asyncio
import httpx
from typing import Callable

APIFY_API_KEY = os.getenv("APIFY_API_KEY", "")
ACTOR_ID = "clockworks/tiktok-scraper"


async def run(job: dict, emit: Callable) -> None:
    """Fetch top 10 TikTok videos (by views, last 90 days) for a creator handle."""
    handle = job["handle"]
    emit("progress", {"stage": "A", "message": f"Fetching @{handle}'s TikTok videos..."})

    async with httpx.AsyncClient(timeout=120) as client:
        # Start Apify actor run
        run_resp = await client.post(
            f"https://api.apify.com/v2/acts/{ACTOR_ID}/runs",
            params={"token": APIFY_API_KEY},
            json={
                "profiles": [handle],
                "resultsPerPage": 30,  # fetch more, sort and take top 10
                "shouldDownloadVideos": False,
                "shouldDownloadCovers": False,
                "scrapeLastNDays": 90,
            },
        )
        run_resp.raise_for_status()
        run_data = run_resp.json()
        run_id = run_data["data"]["id"]
        dataset_id = run_data["data"]["defaultDatasetId"]

        emit(
            "progress",
            {
                "stage": "A",
                "message": f"Scraper started (run {run_id[:8]}...). Waiting for results...",
            },
        )

        # Poll until the run reaches a terminal state (up to 5 minutes)
        for _ in range(60):
            await asyncio.sleep(5)
            status_resp = await client.get(
                f"https://api.apify.com/v2/actor-runs/{run_id}",
                params={"token": APIFY_API_KEY},
            )
            status_resp.raise_for_status()
            status = status_resp.json()["data"]["status"]
            if status == "SUCCEEDED":
                break
            elif status in ("FAILED", "ABORTED", "TIMED-OUT"):
                raise RuntimeError(f"Apify run failed with status: {status}")
        else:
            raise RuntimeError("Apify run timed out after 5 minutes.")

        # Fetch results from the default dataset
        results_resp = await client.get(
            f"https://api.apify.com/v2/datasets/{dataset_id}/items",
            params={"token": APIFY_API_KEY, "limit": 100},
        )
        results_resp.raise_for_status()
        items = results_resp.json()

    # Sort by views descending, take top 10
    videos = sorted(items, key=lambda x: x.get("playCount", 0), reverse=True)[:10]

    # Normalize to a standard schema used by downstream stages
    job["videos"] = [
        {
            "video_id": v.get("id", ""),
            "url": v.get("webVideoUrl", v.get("videoUrl", "")),
            "views": v.get("playCount", 0),
            "likes": v.get("diggCount", 0),
            "comments": v.get("commentCount", 0),
            "shares": v.get("shareCount", 0),
            "duration": v.get("videoMeta", {}).get("duration", 0),
            "description": v.get("text", ""),
            "created_at": v.get("createTimeISO", ""),
            "download_url": v.get("videoUrl", ""),
            "cover_url": v.get("covers", {}).get("default", ""),
        }
        for v in videos
    ]

    emit(
        "progress",
        {
            "stage": "A",
            "message": f"Found {len(job['videos'])} top videos for @{handle}",
            "done": True,
            "count": len(job["videos"]),
        },
    )
