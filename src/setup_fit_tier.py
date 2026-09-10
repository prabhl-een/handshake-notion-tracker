"""
setup_fit_tier.py

One-time setup: creates (or updates) the "Fit Tier" Select property on
your Notion database via the API, with the four color-coded options
already configured -- no manual clicking through Notion's UI required.

Run this once, before (or after) running score_and_sync.py.

Usage:
	python src/setup_fit_tier.py
"""
import os
import sys

import requests
from dotenv import load_dotenv

NOTION_VERSION = "2022-06-28"
NOTION_API_BASE = "https://api.notion.com/v1"

FIT_TIER_OPTIONS = [
	{"name": "🔴 Poor Fit", "color": "red"},
	{"name": "🟠 Weak Fit", "color": "orange"},
	{"name": "🟡 Good Fit", "color": "yellow"},
	{"name": "🟢 Great Fit", "color": "green"},
]


def main():
	load_dotenv()
	token = os.environ.get("NOTION_TOKEN")
	database_id = os.environ.get("NOTION_DATABASE_ID")
	if not token or not database_id:
		print("NOTION_TOKEN / NOTION_DATABASE_ID missing from .env")
		sys.exit(1)

	headers = {
		"Authorization": f"Bearer {token}",
		"Notion-Version": NOTION_VERSION,
		"Content-Type": "application/json",
	}
	payload = {
		"properties": {
			"Fit Tier": {
				"select": {"options": FIT_TIER_OPTIONS}
			}
		}
	}
	resp = requests.patch(
		f"{NOTION_API_BASE}/databases/{database_id}",
		headers=headers, json=payload, timeout=30,
	)
	if not resp.ok:
		print("Error response:", resp.text)
		resp.raise_for_status()

	print("Fit Tier property created/updated with colored options:")
	for opt in FIT_TIER_OPTIONS:
		print(f"  - {opt['name']} ({opt['color']})")


if __name__ == "__main__":
	main()
