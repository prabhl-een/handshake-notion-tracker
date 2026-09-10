import os

import requests
from dotenv import load_dotenv


load_dotenv()

token = os.environ.get("NOTION_TOKEN")
if not token:
	print("NOTION_TOKEN not found in .env -- check that file first.")
	raise SystemExit(1)

resp = requests.post(
	"https://api.notion.com/v1/search",
	headers={
		"Authorization": f"Bearer {token}",
		"Notion-Version": "2022-06-28",
		"Content-Type": "application/json",
	},
	json={"filter": {"value": "database", "property": "object"}},
	timeout=30,
)

print(f"Status: {resp.status_code}\n")

if not resp.ok:
	print("Error response:", resp.text)
	raise SystemExit(1)

results = resp.json().get("results", [])
if not results:
	print("Your integration cannot see ANY databases.")
	print("The 'Connections' share step did not take effect.")
else:
	print(f"Your integration can see {len(results)} database(s):\n")
	for db in results:
		db_id = db.get("id", "?")
		title_parts = db.get("title", [])
		title = "".join(t.get("plain_text", "") for t in title_parts) or "(untitled)"
		print(f' - "{title}"')
		print(f"   ID: {db_id}\n")
