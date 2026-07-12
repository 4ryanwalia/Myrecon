"""
╔══════════════════════════════════════════════════════════════╗
║  Identity Correlator — Cross-Platform Clustering            ║
║  Groups same username across platforms + confidence score   ║
║  Quality-filtered: only high-confidence results shown       ║
╚══════════════════════════════════════════════════════════════╝
"""


class IdentityCorrelator:
    """Groups results by username to form identity clusters with quality filtering."""

    # Minimum confidence threshold — identities below this are dropped
    MIN_CONFIDENCE = 30

    def correlate(self, results: list[dict], target_username: str = "") -> list[dict]:
        """
        Group results by username across platforms.
        Returns ONLY high-quality identity clusters (confidence >= 40%).
        """
        clusters: dict[str, dict] = {}

        for r in results:
            if not r.get("exists", True):
                continue

            # Skip empty/invalid results
            url = r.get("url", "")
            if not url or not url.startswith("http"):
                continue

            # Extract username
            username = r.get("username", "")
            if not username:
                parts = url.rstrip("/").split("/")
                username = parts[-1] if parts else ""
                username = username.lstrip("@").lower()

            if not username or len(username) < 2:
                continue

            # Skip junk usernames (random query params, hashes, etc.)
            if any(c in username for c in ["?", "&", "=", "#", "%", "+"]):
                continue

            key = username.lower()
            if key not in clusters:
                clusters[key] = {
                    "username": username,
                    "platforms": [],
                    "platform_names": [],
                    "confidence": 0,
                    "bio": "",
                    "profile_pic_url": "",
                    "profile_pic_data": b"",
                    "display_name": "",
                    "enriched_data": {},
                    "has_valid_profile": False,
                    "has_metadata": False,
                }

            cluster = clusters[key]
            platform = r.get("platform", r.get("source", "Unknown"))
            category = r.get("category", "mention")

            # Avoid duplicate platforms
            if platform not in cluster["platform_names"]:
                cluster["platform_names"].append(platform)
                cluster["platforms"].append({
                    "platform": platform,
                    "url": url,
                    "category": category,
                })

            # Track quality signals
            if category == "profile" and url.startswith("http"):
                cluster["has_valid_profile"] = True

            # Use the best available enrichment data
            if r.get("bio") and not cluster["bio"]:
                cluster["bio"] = r["bio"]
                cluster["has_metadata"] = True
            if r.get("profile_pic_data") and not cluster["profile_pic_data"]:
                cluster["profile_pic_data"] = r["profile_pic_data"]
                cluster["profile_pic_url"] = r.get("profile_pic_url", "")
                cluster["has_metadata"] = True
            if r.get("display_name") and not cluster["display_name"]:
                cluster["display_name"] = r["display_name"]
                cluster["has_metadata"] = True
            if r.get("followers"):
                cluster["enriched_data"].setdefault("followers", {})
                cluster["enriched_data"]["followers"][platform] = r["followers"]
                cluster["has_metadata"] = True
            if r.get("karma"):
                cluster["enriched_data"]["karma"] = r["karma"]
                cluster["has_metadata"] = True
            if r.get("repos"):
                cluster["enriched_data"]["repos"] = r["repos"]
                cluster["has_metadata"] = True

        # ── Calculate Confidence Scores ──────────────────────────
        target_lower = target_username.lower() if target_username else ""

        for cluster in clusters.values():
            score = 0
            uname = cluster["username"].lower()

            # Exact username match with search target: +30
            if target_lower and uname == target_lower:
                score += 30

            # Has at least one valid profile URL: +30
            if cluster["has_valid_profile"]:
                score += 30

            # Has metadata (bio, followers, profile pic, etc.): +20
            if cluster["has_metadata"]:
                score += 20

            # Multiple platform matches: +20
            n_platforms = len(cluster["platform_names"])
            if n_platforms >= 2:
                score += 20
            elif n_platforms == 1:
                score += 10

            # Bonus: has profile picture: +5
            if cluster["profile_pic_data"]:
                score += 5

            # Bonus: has bio: +5
            if cluster["bio"]:
                score += 5

            # Bonus: has display name: +5
            if cluster["display_name"]:
                score += 5

            # Bonus: more platforms = higher confidence (diminishing returns)
            if n_platforms >= 5:
                score += 10
            elif n_platforms >= 3:
                score += 5

            cluster["confidence"] = min(100, score)

        # ── Quality Filtering ────────────────────────────────────
        # Only keep identities that meet minimum quality standards
        target_lower_f = target_username.lower() if target_username else ""
        high_quality = []
        for cluster in clusters.values():
            # MUST have confidence >= 30%
            if cluster["confidence"] < self.MIN_CONFIDENCE:
                continue

            is_exact_match = target_lower_f and cluster["username"].lower() == target_lower_f

            # Exact username matches get a pass on profile URL requirement
            if not is_exact_match:
                # MUST have at least one valid profile URL
                if not cluster["has_valid_profile"]:
                    continue

            # Skip clusters with only "mention" category and no metadata
            # (unless it's an exact username match)
            all_mentions = all(p["category"] == "mention" for p in cluster["platforms"])
            if all_mentions and not cluster["has_metadata"] and not is_exact_match:
                continue

            high_quality.append(cluster)

        # Sort by confidence descending, then by platform count
        high_quality.sort(
            key=lambda c: (c["confidence"], len(c["platform_names"])),
            reverse=True,
        )

        return high_quality
