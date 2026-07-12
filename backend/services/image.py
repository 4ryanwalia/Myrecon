"""
╔══════════════════════════════════════════════════════════════╗
║  Image Service — Reverse Image Search API Layer              ║
║  Synchronous, serverless-safe (no threads, no global state)  ║
╚══════════════════════════════════════════════════════════════╝
"""

import os
import sys

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.reverse_image import ReverseImageSearch
from utils.parser import categorise_result


def scan_image(image_url: str, deep: bool = False) -> dict:
    """
    Run reverse image search pipeline:
      1. Google Image Search
      2. Web search for pages linking the image
      3. Keyword-based image search
      4. (Deep) additional results

    Args:
        image_url: URL of the image to reverse-search
        deep: whether to fetch additional result pages

    Returns a clean JSON-serializable dict.
    """
    if not image_url or not image_url.startswith("http"):
        return {
            "status": "error",
            "error": "Please provide a valid image URL (starting with http:// or https://)",
            "query": {"image_url": image_url},
        }

    api_key = os.environ.get("GOOGLE_API_KEY", "")
    cx_id = os.environ.get("GOOGLE_CX_ID", "")
    if not api_key or not cx_id:
        return {
            "status": "error",
            "error": "Reverse image search requires a Google Custom Search key on the server.",
            "query": {"image_url": image_url, "deep": deep},
        }

    try:
        engine = ReverseImageSearch(api_key=api_key, cx_id=cx_id, delay=0.5)
        results = engine.scan(image_url, deep=deep)
    except Exception as e:
        return {
            "status": "error",
            "error": f"Image scan failed: {e}",
            "query": {"image_url": image_url, "deep": deep},
        }

    # Categorize and clean
    for r in results:
        r["category"] = categorise_result(r)
        r.pop("profile_pic_data", None)

    profiles = [r for r in results if r.get("category") == "profile"]
    mentions = [r for r in results if r.get("category") == "mention"]

    return {
        "status": "ok",
        "query": {"image_url": image_url, "deep": deep},
        "summary": {
            "total": len(results),
            "profiles": len(profiles),
            "mentions": len(mentions),
        },
        "results": results,
    }
