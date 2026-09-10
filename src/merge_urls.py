"""
merge_urls.py

Merges real Handshake URLs (from scripts/handshake_page_collector.js,
which reads links + surrounding card text while paging through the
list -- no clicking into individual jobs) into your existing jobs.json.

Matching is by (title, company) together when both are available, since
title alone can collide across different employers. Falls back to
title-only matching if a collected entry has no company.

Usage:
    python src/merge_urls.py --jobs jobs.json --urls handshake_urls.json --output jobs.json
"""
import argparse
import json
from pathlib import Path


def normalize(s: str) -> str:
    return " ".join((s or "").lower().split())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--jobs", default="jobs.json")
    parser.add_argument("--urls", required=True)
    parser.add_argument("--output", default="jobs.json")
    args = parser.parse_args()

    jobs = json.loads(Path(args.jobs).read_text(encoding="utf-8"))
    url_entries = json.loads(Path(args.urls).read_text(encoding="utf-8"))

    # Prefer (title, company) keys; keep a title-only fallback map too.
    pair_lookup = {}
    title_only_lookup = {}
    for e in url_entries:
        title_key = normalize(e.get("listTitle", ""))
        company_key = normalize(e.get("company", ""))
        url = e.get("handshakeUrl")
        if not title_key or not url:
            continue
        if company_key:
            pair_lookup[(title_key, company_key)] = url
        title_only_lookup.setdefault(title_key, url)

    matched = 0
    unmatched = []

    for job in jobs:
        title_key = normalize(job.get("title", ""))
        company_key = normalize(job.get("company", ""))

        url = pair_lookup.get((title_key, company_key))
        if not url:
            url = title_only_lookup.get(title_key)

        if url:
            job["handshake_url"] = url
            matched += 1
        else:
            unmatched.append(job.get("title", "(no title)"))

    Path(args.output).write_text(json.dumps(jobs, indent=2), encoding="utf-8")
    print(f"Matched {matched}/{len(jobs)} jobs with URLs.")
    if unmatched:
        print(f"\n{len(unmatched)} job(s) had no matching URL (title/company mismatch?):")
        for t in unmatched[:20]:
            print(f"  - {t}")
        if len(unmatched) > 20:
            print(f"  ...and {len(unmatched) - 20} more")


if __name__ == "__main__":
    main()