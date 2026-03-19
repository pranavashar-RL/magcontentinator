"""Stage: Library Intelligence — rule-based archetype → pain point → combo → hook pool assembly."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from ashwamag_config import get_archetype_group, get_library_intel, build_library_context, ARCHETYPE_PAIN_POINTS, ARCHETYPE_COMBOS
from typing import Callable

CONFIDENCE_THRESHOLD = 0.70
MIN_VIDEOS = 5


def run_sync(job: dict, emit: Callable) -> None:
    """Synchronous — library assembly is pure Python, no I/O."""
    profile = job.get("profile", {})
    archetype = profile.get("archetype", "everyday_consumer")
    confidence = profile.get("archetype_confidence", 0.0)
    videos_analyzed = len(job.get("analyzed_videos", []))

    emit("progress", {"stage": "LIB", "message": "Assembling library intelligence..."})

    if confidence < CONFIDENCE_THRESHOLD or videos_analyzed < MIN_VIDEOS:
        job["library_intel"] = None
        emit("progress", {
            "stage": "LIB",
            "message": (
                f"Archetype confidence {confidence:.0%} < threshold or insufficient videos "
                f"({videos_analyzed}). Skipping library."
            ),
            "library_available": False,
        })
        return

    group = get_archetype_group(archetype)

    # Build 3 brief assignments
    briefs = {}
    for i in range(1, 4):
        intel = get_library_intel(archetype, i)
        briefs[f"brief_{i}"] = {
            **intel,
            "context_str": build_library_context(archetype, i),
        }

    job["library_intel"] = {
        "archetype": archetype,
        "archetype_group": group,
        "confidence": confidence,
        "briefs": briefs,
        "available": True,
    }

    emit("library_intel", {
        "available": True,
        "archetype": archetype,
        "archetype_group": group,
        "confidence": confidence,
        "briefs": {
            k: {
                "pain_point": v["pain_point"],
                "combo": v["combo"],
                "pain_total_gmv": v["pain_total_gmv"],
                "pain_avg_gmv": v["pain_avg_gmv"],
                "combo_gmv": v["combo_gmv"],
            }
            for k, v in briefs.items()
        },
    })
    emit("progress", {
        "stage": "LIB",
        "message": f"Library intel ready for {group} archetype group.",
        "done": True,
    })


async def run(job: dict, emit: Callable) -> None:
    run_sync(job, emit)
