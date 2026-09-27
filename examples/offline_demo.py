"""Explain MyRecon verdicts with synthetic data; never performs a lookup."""

import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print the labeled sample as JSON")
    args = parser.parse_args()
    fixture = Path(__file__).with_name("sample_verdicts.json")
    data = json.loads(fixture.read_text(encoding="utf-8"))
    if args.json:
        print(json.dumps(data, indent=2))
        return
    print("MYRECON OFFLINE DEMO | SYNTHETIC SAMPLE DATA")
    print("No network requests. No real accounts. Not a live scan.\n")
    for result in data["results"]:
        print(f"{result['verdict']:9} {result['platform']}")
        print(f"          {result['evidence']}")
        print(f"          Next: {result['next_step']}\n")
    print(" | ".join(
        f"{sum(row['verdict'] == verdict for row in data['results'])} {verdict}"
        for verdict in ("found", "not_found", "unknown")
    ))
    print("A shared handle does not establish a shared identity.")


if __name__ == "__main__":
    main()
