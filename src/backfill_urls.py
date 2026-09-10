"""
backfill_urls.py

notion_sync.py only fills in fields when CREATING a new row -- it skips
existing rows entirely to avoid clobbering your manual edits. That
means jobs you synced before running merge_urls.py won't have a
Handshake URL yet. This script catches those up: it matches existing
Notion rows to your local jobs.json by (title, company), and sets
Handshake URL only where Notion's value is currently empty.

Usage:
    python src/backfill_urls.py --jobs jobs.json --dry-run
    python src/backfill_urls.py --jobs jobs.json
"""
import argparse
import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

NOTION_VERSION = "2022-06-28"
NOTION_API_BASE = "https://api.notion.com/v1"


def _extract_title(prop):
    if not prop or prop.get("type") != "title":
        return ""
    return "".join(p.get("plain_text", "") for p in prop.get("title", []))


def _extract_text(prop):
    if not prop:
        return ""
    if prop.get("type") == "rich_text":
        return "".join(p.get("plain_text", "") for p in prop.get("rich_text", []))
    return ""


def _extract_url(prop):
    if not prop or prop.get("type") != "url":
        return None
    return prop.get("url")


def fetch_all_pages(token, database_id):
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }
    pages = []
    has_more = True
    start_cursor = None
    while has_more:
        payload = {"page_size": 100}
        if start_cursor:
            payload["start_cursor"] = start_cursor
        resp = requests.post(
            f"{NOTION_API_BASE}/databases/{database_id}/query",
            headers=headers, json=payload, timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        pages.extend(data.get("results", []))
        has_more = data.get("has_more", False)
        start_cursor = data.get("next_cursor")
    return pages


def update_url(token, page_id, url):
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }
    payload = {"properties": {"Handshake URL": {"url": url}}}
    resp = requests.patch(
        f"{NOTION_API_BASE}/pages/{page_id}", headers=headers, json=payload, timeout=30
    )
    resp.raise_for_status()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--jobs", default="jobs.json")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    load_dotenv()
    token = os.environ.get("NOTION_TOKEN")
    database_id = os.environ.get("NOTION_DATABASE_ID")
    if not token or not database_id:
        print("NOTION_TOKEN / NOTION_DATABASE_ID missing from .env")
        sys.exit(1)

    jobs = json.loads(Path(args.jobs).read_text(encoding="utf-8"))
    lookup = {}
    for job in jobs:
        key = (job.get("title", "").strip().lower(), job.get("company", "").strip().lower())
        lookup[key] = job

    pages = fetch_all_pages(token, database_id)
    print(f"Found {len(pages)} jobs in Notion.\n")

    updated = skipped_no_match = skipped_no_url = skipped_already_set = 0

    for page in pages:
        props = page.get("properties", {})
        title = _extract_title(props.get("Job Title"))
        company = _extract_text(props.get("Company"))
        existing_url = _extract_url(props.get("Handshake URL"))
        key = (title.strip().lower(), company.strip().lower())
        job = lookup.get(key)

        if not job:
            skipped_no_match += 1
            continue
        new_url = job.get("handshake_url")
        if not new_url:
            skipped_no_url += 1
            continue
        if existing_url:
            skipped_already_set += 1
            continue

        label = f"{'Would set' if args.dry_run else 'Setting'} URL for: {title} @ {company}"
        print(label)
        if not args.dry_run:
            update_url(token, page["id"], new_url)
        updated += 1

    print(f"\n{'Would update' if args.dry_run else 'Updated'}: {updated}")
    print(f"Skipped (no matching local job): {skipped_no_match}")
    print(f"Skipped (no URL available locally): {skipped_no_url}")
    print(f"Skipped (Notion already had a URL): {skipped_already_set}")


if __name__ == "__main__":
    main()