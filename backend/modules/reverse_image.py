"""
╔══════════════════════════════════════════════════════════════╗
║  Reverse Image Search — Google Custom Search API             ║
║  Uses searchType=image to find visually similar images       ║
║  and their source pages for OSINT correlation                ║
╚══════════════════════════════════════════════════════════════╝
"""

import time
import requests
from typing import Optional

GOOGLE_CSE_URL = "https://www.googleapis.com/customsearch/v1"


class ReverseImageSearch:
    """
    Performs reverse image search using Google Custom Search API.
    Accepts an image URL or local file path, searches Google for
    visually similar images, and extracts source page links.
    """

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
    }
    TIMEOUT = 15

    def __init__(self, api_key: str = "", cx_id: str = "", delay: float = 0.5):
        import os
        # Keys come only from the caller or the environment — never hardcoded.
        self.api_key = api_key or os.environ.get("GOOGLE_API_KEY", "")
        self.cx_id = cx_id or os.environ.get("GOOGLE_CX_ID", "")
        self.delay = delay
        self.results: list[dict] = []
        self._stop_flag = False

    def stop(self):
        self._stop_flag = True

    # ──────────────────────────────────────────────────────────
    #  Core: Google Image Search by URL
    # ──────────────────────────────────────────────────────────

    def _search_by_image_url(self, image_url: str, start: int = 1) -> list[dict]:
        """Search Google CSE for pages containing/matching this image."""
        hits = []

        if not self.api_key or not self.cx_id:
            hits.append({
                "url": "", "title": "API key not configured",
                "snippet": "Google API key or CX ID missing",
                "source": "reverse_image", "error": True,
            })
            return hits

        try:
            # Method 1: Image search using the image URL as query
            params = {
                "key": self.api_key,
                "cx": self.cx_id,
                "q": image_url,
                "searchType": "image",
                "num": 10,
                "start": start,
            }

            resp = requests.get(GOOGLE_CSE_URL, params=params,
                                headers=self.HEADERS, timeout=self.TIMEOUT)
            data = resp.json()

            if "items" in data:
                for item in data["items"]:
                    hits.append({
                        "url": item.get("image", {}).get("contextLink", ""),
                        "image_url": item.get("link", ""),
                        "title": item.get("title", ""),
                        "snippet": item.get("snippet", ""),
                        "display_link": item.get("displayLink", ""),
                        "width": item.get("image", {}).get("width", 0),
                        "height": item.get("image", {}).get("height", 0),
                        "source": "reverse_image",
                        "platform": item.get("displayLink", "Image Match"),
                        "exists": True,
                        "category": "profile",
                    })
            elif "error" in data:
                err_msg = data["error"].get("message", "Unknown error")
                hits.append({
                    "url": "", "title": f"API Error: {err_msg}",
                    "snippet": "", "source": "reverse_image", "error": True,
                })

        except Exception as e:
            hits.append({
                "url": "", "title": f"Error: {e}",
                "snippet": "", "source": "reverse_image", "error": True,
            })

        return hits

    def _search_web_for_image(self, image_url: str, start: int = 1) -> list[dict]:
        """Regular web search using the image URL to find pages linking it."""
        hits = []

        if not self.api_key or not self.cx_id:
            return hits

        try:
            params = {
                "key": self.api_key,
                "cx": self.cx_id,
                "q": f'"{image_url}"',
                "num": 10,
                "start": start,
            }

            resp = requests.get(GOOGLE_CSE_URL, params=params,
                                headers=self.HEADERS, timeout=self.TIMEOUT)
            data = resp.json()

            if "items" in data:
                for item in data["items"]:
                    hits.append({
                        "url": item.get("link", ""),
                        "title": item.get("title", ""),
                        "snippet": item.get("snippet", ""),
                        "display_link": item.get("displayLink", ""),
                        "source": "reverse_image",
                        "platform": item.get("displayLink", "Web Match"),
                        "exists": True,
                        "category": "mention",
                    })

        except Exception:
            pass

        return hits

    def _search_image_keywords(self, image_url: str) -> list[dict]:
        """Search using extracted keywords from the image URL path."""
        hits = []

        if not self.api_key or not self.cx_id:
            return hits

        # Extract potential keywords from URL path
        from urllib.parse import urlparse, unquote
        parsed = urlparse(image_url)
        path = unquote(parsed.path)
        # Get filename without extension
        parts = path.split("/")
        filename = parts[-1] if parts else ""
        name = filename.rsplit(".", 1)[0] if "." in filename else filename
        # Clean up common separators
        keywords = name.replace("-", " ").replace("_", " ").replace("%20", " ").strip()

        if not keywords or len(keywords) < 3:
            return hits

        try:
            params = {
                "key": self.api_key,
                "cx": self.cx_id,
                "q": keywords,
                "searchType": "image",
                "num": 10,
            }

            resp = requests.get(GOOGLE_CSE_URL, params=params,
                                headers=self.HEADERS, timeout=self.TIMEOUT)
            data = resp.json()

            if "items" in data:
                for item in data["items"]:
                    hits.append({
                        "url": item.get("image", {}).get("contextLink", ""),
                        "image_url": item.get("link", ""),
                        "title": item.get("title", ""),
                        "snippet": item.get("snippet", ""),
                        "display_link": item.get("displayLink", ""),
                        "source": "reverse_image",
                        "platform": item.get("displayLink", "Keyword Match"),
                        "exists": True,
                        "category": "mention",
                    })

        except Exception:
            pass

        return hits

    # ──────────────────────────────────────────────────────────
    #  Full Reverse Image Scan
    # ──────────────────────────────────────────────────────────

    def scan(self, image_input: str, callback=None, deep: bool = False) -> list[dict]:
        """
        Run the full reverse image search pipeline.

        Args:
            image_input: Image URL or local file path
            callback: Progress callback function
            deep: If True, perform additional search passes
        """
        self._stop_flag = False
        all_results = []

        # Determine if input is URL or file path
        is_url = image_input.startswith("http://") or image_input.startswith("https://")

        if not is_url:
            # Local file — we can't directly reverse-search a local file via API
            if callback:
                callback(
                    module="Reverse Image",
                    message="Local file detected — upload to an image host first for best results",
                    progress=0, results=[],
                )
            # Try keyword extraction from filename
            from pathlib import Path
            filename = Path(image_input).stem
            keywords = filename.replace("-", " ").replace("_", " ")
            if len(keywords) >= 3:
                if callback:
                    callback(
                        module="Reverse Image",
                        message=f"Searching by filename keywords: '{keywords}'",
                        progress=10, results=[],
                    )
                try:
                    params = {
                        "key": self.api_key,
                        "cx": self.cx_id,
                        "q": keywords,
                        "searchType": "image",
                        "num": 10,
                    }
                    resp = requests.get(GOOGLE_CSE_URL, params=params,
                                        headers=self.HEADERS, timeout=self.TIMEOUT)
                    data = resp.json()
                    if "items" in data:
                        for item in data["items"]:
                            r = {
                                "url": item.get("image", {}).get("contextLink", ""),
                                "image_url": item.get("link", ""),
                                "title": item.get("title", ""),
                                "snippet": item.get("snippet", ""),
                                "platform": item.get("displayLink", "Keyword Match"),
                                "source": "reverse_image",
                                "exists": True,
                                "category": "mention",
                            }
                            all_results.append(r)
                    if callback:
                        callback(
                            module="Reverse Image",
                            message=f"Found {len(all_results)} results from filename keywords",
                            progress=100, results=all_results,
                        )
                except Exception as e:
                    if callback:
                        callback(
                            module="Reverse Image",
                            message=f"Keyword search error: {e}",
                            progress=100, results=[],
                        )
            else:
                if callback:
                    callback(
                        module="Reverse Image",
                        message="Cannot extract keywords from filename — provide an image URL instead",
                        progress=100, results=[],
                    )

            self.results = all_results
            return all_results

        # ── URL-based reverse image search ──

        # Phase 1: Google Image Search
        if not self._stop_flag:
            if callback:
                callback(
                    module="Reverse Image",
                    message="[1/3] Searching Google Images...",
                    progress=10, results=[],
                )
            image_hits = self._search_by_image_url(image_input)
            real_hits = [h for h in image_hits if not h.get("error")]
            all_results.extend(real_hits)

            if callback:
                callback(
                    module="Reverse Image",
                    message=f"[1/3] Found {len(real_hits)} image matches",
                    progress=35, results=real_hits,
                )
            time.sleep(self.delay)

        # Phase 2: Web search for pages linking the image
        if not self._stop_flag:
            if callback:
                callback(
                    module="Reverse Image",
                    message="[2/3] Searching web for pages using this image...",
                    progress=40, results=[],
                )
            web_hits = self._search_web_for_image(image_input)
            all_results.extend(web_hits)

            if callback:
                callback(
                    module="Reverse Image",
                    message=f"[2/3] Found {len(web_hits)} web page matches",
                    progress=65, results=web_hits,
                )
            time.sleep(self.delay)

        # Phase 3: Keyword-based image search (extract from URL)
        if not self._stop_flag:
            if callback:
                callback(
                    module="Reverse Image",
                    message="[3/3] Searching by image URL keywords...",
                    progress=70, results=[],
                )
            kw_hits = self._search_image_keywords(image_input)
            all_results.extend(kw_hits)

            if callback:
                callback(
                    module="Reverse Image",
                    message=f"[3/3] Found {len(kw_hits)} keyword matches",
                    progress=90, results=kw_hits,
                )
            time.sleep(self.delay)

        # Deep mode: fetch page 2 of image results
        if deep and not self._stop_flag and len(all_results) > 0:
            if callback:
                callback(
                    module="Reverse Image",
                    message="[DEEP] Fetching additional image results...",
                    progress=92, results=[],
                )
            extra = self._search_by_image_url(image_input, start=11)
            real_extra = [h for h in extra if not h.get("error")]
            all_results.extend(real_extra)
            if callback:
                callback(
                    module="Reverse Image",
                    message=f"[DEEP] Found {len(real_extra)} additional matches",
                    progress=98, results=real_extra,
                )

        # Deduplicate by URL
        seen = set()
        unique = []
        for r in all_results:
            url = r.get("url", "")
            if url and url not in seen:
                seen.add(url)
                unique.append(r)

        # Final summary
        if callback:
            callback(
                module="Reverse Image",
                message=f"Reverse image search complete — {len(unique)} unique results",
                progress=100, results=[],
            )

        self.results = unique
        return unique
