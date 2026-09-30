"""Record explicit source controls for the manually inspected case-study pages.

This opt-in review never takes a competing tool's verdict as reference truth.
Matching profile markup plus a missing synthetic control supports a public
profile. Generic titles, blocks, SPA shells and handle echoes remain unknown.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

import requests

from review_username_benchmark import address, observe
from username_benchmark import write


def review(folder, handle):
    path = folder / "source-reviews.json"
    reviews = json.loads(path.read_text())
    control = "mrbench-a7b32c91d8e04f6a"
    urls = [f"https://x.com/{handle}", f"https://gist.github.com/{handle}",
            f"https://{handle}.itch.io", f"https://www.openstreetmap.org/user/{handle}",
            f"https://buymeacoffee.com/{handle}", f"https://hackerone.com/{handle}"]
    for url in urls:
        target, negative = observe(url, handle), observe(url.replace(handle, control), control)
        key = address(url)
        named = handle.casefold() in target.get("title", "").casefold()
        # These fields name the account, rather than echoing the request URL.
        if "hackerone.com" in url:
            with requests.get(url, headers={"User-Agent": "MyRecon-public-benchmark-review/1.0"}, timeout=(6, 8)) as response:
                named = bool(re.search(r'property="og:profile:username"\s+content="' + re.escape(handle) + '"', response.text))
                target["profile_field_sha256"] = hashlib.sha256(response.content).hexdigest()
        if "buymeacoffee.com" in url:
            named = bool(target.get("title")) and " is " in target["title"]
        if target.get("status_code") == 200 and named and negative["verdict"] == "not_found":
            target.update(verdict="found", evidence="profile_identity_with_missing_control",
                note="Reviewed account-specific profile title/markup; the synthetic control returns explicit absence. Ownership is unverified.")
        target["control"] = negative
        reviews[key] = target
        print(key, target["verdict"], target["evidence"], flush=True)
    # F3 serves only a parking redirect for both target and synthetic control.
    # This is contradicted as a public-profile lead, not an ownership judgment.
    for url in (f"https://f3.cool/{handle}/", f"https://mastodon.cloud/@{handle}"):
        target, negative = observe(url, handle), observe(url.replace(handle, control), control)
        with requests.get(url, timeout=(6, 8)) as response:
            parking_redirect = 'window.location.href="/lander"' in response.text
        parked_mastodon = target.get("final_url", "").startswith("https://media.mastodon.cloud/cloud-")
        if target.get("status_code") == negative.get("status_code") == 200 and target.get("body_sha256") == negative.get("body_sha256") and (parking_redirect or parked_mastodon):
            target.update(verdict="not_found", evidence="non_profile_destination_with_identical_control",
                note="Target and synthetic control return the same non-profile parking/media destination. This response does not expose the reported account.")
        target["control"] = negative
        reviews[address(url)] = target
        print(address(url), target["verdict"], target["evidence"], flush=True)
    # Periscope's URL currently resolves to X, not a distinct Periscope profile.
    periscope = reviews.get(address(f"https://www.periscope.tv/{handle}"))
    if periscope and address(periscope.get("final_url", "")) == address(f"https://x.com/{handle}"):
        periscope.update(verdict="found", evidence="redirect_to_supported_profile",
            note="Redirects to the source-supported X profile. This is not evidence of a separate Periscope account.")
    write(path, reviews)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    review(args.output_dir, args.username)
