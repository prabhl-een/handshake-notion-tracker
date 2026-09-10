"""
score_and_sync.py

Scores every job currently in your Notion database against your resume
using free keyword-overlap matching (resume_matcher.py), then writes
each score back into that row's "Fit Tier" property as a color-coded tag.

Notion only stores Job Title and Company (per our schema) -- the fuller
pay/employment type/location fields live in your local jobs.json from
the last parse. This script cross-references the two by (title, company)
so scoring has a bit more to work with than the title alone. If a job
isn't found in jobs.json (e.g. you've since deleted that file), it just
scores against the title.

Usage:
    python src/score_and_sync.py --resume resume.txt --dry-run   # preview only
    python src/score_and_sync.py --resume resume.txt              # writes to Notion
"""

import argparse
import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent))
from resume_matcher import score_fit

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


def load_jobs_json_lookup(path="jobs.json"):
    p = Path(path)
    if not p.exists():
        return {}
    try:
        jobs = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    lookup = {}
    for job in jobs:
        key = (job.get("title", "").strip().lower(), job.get("company", "").strip().lower())
        lookup[key] = job
    return lookup


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


def _fit_tier(score_pct: int) -> str:
    """Maps a 0-100 score to one of the four color-coded Select options.
    These exact strings must match the option names in Notion's Fit Tier
    property (set up via setup_fit_tier.py)."""
    if score_pct >= 76:
        return "🟢 Great Fit"
    if score_pct >= 51:
        return "🟡 Good Fit"
    if score_pct >= 26:
        return "🟠 Weak Fit"
    return "🔴 Poor Fit"


def update_fit_score(token, page_id, score_pct):
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }
    payload = {"properties": {"Fit Tier": {"select": {"name": _fit_tier(score_pct)}}}}
    resp = requests.patch(
        f"{NOTION_API_BASE}/pages/{page_id}", headers=headers, json=payload, timeout=30
    )
    resp.raise_for_status()


def main():
    parser = argparse.ArgumentParser(description="Score all Notion jobs against your resume")
    parser.add_argument("--resume", required=True, help="Path to your resume as plain text")
    parser.add_argument("--dry-run", action="store_true", help="Preview scores without writing to Notion")
    args = parser.parse_args()

    load_dotenv()
    token = os.environ.get("NOTION_TOKEN")
    database_id = os.environ.get("NOTION_DATABASE_ID")
    if not token or not database_id:
        print("NOTION_TOKEN / NOTION_DATABASE_ID missing from .env")
        sys.exit(1)

    resume_path = Path(args.resume)
    if not resume_path.exists():
        print(f"Resume file not found: {args.resume}")
        sys.exit(1)
    resume_text = resume_path.read_text(encoding="utf-8")

    lookup = load_jobs_json_lookup()

    pages = fetch_all_pages(token, database_id)
    print(f"Found {len(pages)} jobs in Notion.\n")

    for page in pages:
        props = page.get("properties", {})
        title = _extract_title(props.get("Job Title"))
        company = _extract_text(props.get("Company"))
        key = (title.strip().lower(), company.strip().lower())
        extra = lookup.get(key)

        job_text = title
        if extra:
            if extra.get("description"):
                job_text = f"{title} {extra['description']}"
            else:
                job_text = " ".join(filter(None, [
                    title,
                    extra.get("pay") or "",
                    extra.get("employment_type") or "",
                ]))

        score = score_fit(resume_text, job_text)
        print(f"{score:3d}%  {title} @ {company}")

        if not args.dry_run:
            update_fit_score(token, page["id"], score)

    if args.dry_run:
        print("\n(dry run -- nothing written to Notion)")
    else:
        print(f"\nUpdated Fit % for {len(pages)} jobs in Notion.")


if __name__ == "__main__":
    main()