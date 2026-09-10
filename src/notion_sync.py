"""
notion_sync.py

Pushes parsed job dicts (see parser.py) into a Notion database via the
Notion API, without creating duplicate rows.

Expected Notion database schema (property name -> type):
    Job Title      -> Title
    Company        -> Text
    Deadline       -> Date
    Status         -> Select (e.g. Not Applied / Applied / Interviewing / Offer / Rejected)
    Fit %          -> Number (percent)
    Notes          -> Text
    Handshake URL  -> URL
    Pay            -> Text        (optional, created if you add the column)
    Location       -> Text        (optional)

Only Job Title, Company, Deadline, and Handshake URL are written by
this script automatically. Status defaults to "Not Applied" on create
and is never overwritten on an existing row, so your manual status
updates are never clobbered by a re-sync.
"""

import os
import requests

NOTION_VERSION = "2022-06-28"
NOTION_API_BASE = "https://api.notion.com/v1"


class NotionSync:
    def __init__(self, token: str = None, database_id: str = None):
        self.token = token or os.environ.get("NOTION_TOKEN")
        self.database_id = database_id or os.environ.get("NOTION_DATABASE_ID")
        if not self.token or not self.database_id:
            raise ValueError(
                "NOTION_TOKEN and NOTION_DATABASE_ID must be set (env vars or .env file)."
            )
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        }

    def _existing_keys(self) -> set:
        """
        Query the database and build a set of (title, company) keys,
        lowercased, for every existing row. Used to skip duplicates.
        """
        keys = set()
        has_more = True
        start_cursor = None

        while has_more:
            payload = {"page_size": 100}
            if start_cursor:
                payload["start_cursor"] = start_cursor

            resp = requests.post(
                f"{NOTION_API_BASE}/databases/{self.database_id}/query",
                headers=self.headers,
                json=payload,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()

            for page in data.get("results", []):
                props = page.get("properties", {})
                title = _extract_title(props.get("Job Title"))
                company = _extract_text(props.get("Company"))
                if title and company:
                    keys.add((title.strip().lower(), company.strip().lower()))

            has_more = data.get("has_more", False)
            start_cursor = data.get("next_cursor")

        return keys

    def push_jobs(self, jobs: list, dry_run: bool = False) -> dict:
        """
        jobs: list of dicts as produced by parser.jobs_to_dicts().
        Returns a summary dict: {"created": N, "skipped": N, "errors": [...]}
        """
        existing = self._existing_keys()
        created, skipped, errors = 0, 0, []

        for job in jobs:
            key = (job["title"].strip().lower(), job["company"].strip().lower())
            if key in existing:
                skipped += 1
                continue

            if dry_run:
                print(f"[dry-run] Would create: {job['title']} @ {job['company']}")
                created += 1
                continue

            try:
                self._create_page(job)
                created += 1
                existing.add(key)  # avoid dupes within the same run
            except requests.HTTPError as e:
                errors.append(f"{job['title']} @ {job['company']}: {e}")

        return {"created": created, "skipped": skipped, "errors": errors}

    def _create_page(self, job: dict):
        properties = {
            "Job Title": {"title": [{"text": {"content": job["title"][:2000]}}]},
            "Company": {"rich_text": [{"text": {"content": job["company"][:2000]}}]},
            "Status": {"select": {"name": "Not Applied"}},
        }
        if job.get("deadline"):
            properties["Deadline"] = {"date": {"start": job["deadline"]}}
        if job.get("handshake_url"):
            properties["Handshake URL"] = {"url": job["handshake_url"]}

        payload = {
            "parent": {"database_id": self.database_id},
            "properties": properties,
        }
        resp = requests.post(
            f"{NOTION_API_BASE}/pages", headers=self.headers, json=payload, timeout=30
        )
        resp.raise_for_status()


def _extract_title(prop) -> str:
    if not prop or prop.get("type") != "title":
        return ""
    parts = prop.get("title", [])
    return "".join(p.get("plain_text", "") for p in parts)


def _extract_text(prop) -> str:
    if not prop:
        return ""
    if prop.get("type") == "rich_text":
        parts = prop.get("rich_text", [])
        return "".join(p.get("plain_text", "") for p in parts)
    return ""
