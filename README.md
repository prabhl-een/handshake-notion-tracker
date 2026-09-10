# Job Application Tracker

A pipeline that turns copy-pasted Handshake job listings into a structured,
sortable Notion database — with a built-in (and upgradeable) resume fit
scorer. Built to remove the busywork of manually retyping saved jobs into
a tracker, while staying within Handshake's terms of service (no login
automation/scraping — you control exactly what data goes in).

## Why this exists

Handshake doesn't offer a personal API or OAuth connection for a student's
saved jobs, and Notion's Web Clipper only fills in a page title, not
structured columns. This project bridges that gap: paste your saved-jobs
page text once, and it parses, deduplicates, and pushes clean rows straight
into Notion — no manual retyping of company names, deadlines, or pay.

## Architecture

```
raw Handshake text (copy-paste)
        │
        ▼
   src/parser.py        --  regex-based extraction + dedup + date normalization
        │
        ▼
   jobs.json             --  reviewable intermediate artifact
        │
        ▼
   src/notion_sync.py    --  upserts new rows into your Notion database via the Notion API
        │
        ▼
   Notion database        --  sortable by Deadline / Status / Fit % via native views

   src/resume_matcher.py --  (optional) keyword-overlap fit scoring, run separately
```

## Setup

1. **Clone and install dependencies**
   ```bash
   git clone <your-repo-url>
   cd job-tracker
   pip install -r requirements.txt
   ```

2. **Create a Notion integration**
   - Go to https://www.notion.so/my-integrations → "New integration"
   - Copy the generated secret

3. **Create your Notion database** with these exact property names:

   | Property        | Type   |
   |------------------|--------|
   | Job Title        | Title  |
   | Company          | Text   |
   | Deadline         | Date   |
   | Status           | Select (options: Not Applied, Applied, Interviewing, Offer, Rejected) |
   | Fit %            | Number (format: Percent) |
   | Notes            | Text   |
   | Handshake URL    | URL    |

   Then share the database with your integration: open the database →
   `...` menu → **Connections** → add your integration.

4. **Configure credentials**
   ```bash
   cp .env.example .env
   # fill in NOTION_TOKEN and NOTION_DATABASE_ID
   ```

## Usage

**Step 1 — Parse.** Select all the text on your Handshake "Saved Jobs" page,
paste it into a text file, then:
```bash
python src/main.py parse --input raw_handshake.txt --output jobs.json
```
Open `jobs.json` and skim it — the parser is heuristic (see
[Limitations](#limitations)), so fix anything that looks off before syncing.

**Step 2 — Sync to Notion.**
```bash
python src/main.py sync --input jobs.json --dry-run   # preview first
python src/main.py sync --input jobs.json              # actually write
```
Re-running `sync` on an updated paste is safe — jobs already in your
database (matched on title + company) are skipped, not duplicated. Your
manual Status/Notes edits are never touched.

**Step 3 — (Optional) Score resume fit.**
```bash
python src/main.py score --resume resume.txt --job job_description.txt
```
This prints a 0-100 keyword-overlap score. See [Limitations](#limitations)
for why this is a rough signal, not a hiring prediction.

## Auto-collecting all pages (optional, saves manual copy-pasting)

Instead of copy-pasting each page of Handshake search results by hand, you
can run `scripts/handshake_page_collector.js` in your browser's DevTools
console while on your Saved Jobs page. It clicks through every page for you
and downloads one combined `handshake_saved_jobs_raw.txt` file, ready to
feed into `parse`.

This runs entirely inside your own logged-in browser tab -- it doesn't
store or transmit your credentials, and there's no separate automated
login step, unlike a headless scraping bot. It's still automated
interaction with the page, so this is offered as a convenience for your
own data, not a guarantee it fits every reading of Handshake's terms of
service. See the comments at the top of the script for exact steps and
what to do if the "Next page" button isn't found (Handshake's markup can
change, so you may need to tweak one selector).

## Running it in VS Code (no terminal typing required)

The repo includes `.vscode/launch.json` with every pipeline step pre-built
as a one-click Run configuration.

1. Open the `job-tracker` folder in VS Code (`File > Open Folder...`).
2. Install the **Python** extension (Extensions icon in the sidebar, search
   "Python", click Install) if you don't have it.
3. Open the Command Palette (`Ctrl+Shift+P` / `Cmd+Shift+P`), run
   **"Python: Create Environment..."**, choose Venv, and when it asks about
   `requirements.txt`, say yes — this creates a virtual environment and
   installs all dependencies for you, no typing needed.
4. Click the **Run and Debug** icon in the left sidebar (the triangle with a
   bug). At the top you'll see a dropdown of the five pre-built
   configurations (Parse sample data, Parse my jobs, Sync dry-run, etc.).
   Pick one and click the green ▶ play button.
5. For step "2. Parse MY jobs," first create a file called `my_jobs.txt` in
   the project root (right-click the file explorer > New File) and paste
   your real Handshake text into it, then run that configuration.
6. For step "5. Score resume fit," create `resume.txt` and
   `job_description.txt` the same way before running it.
7. To run the tests without typing: click the **Testing** icon in the left
   sidebar (looks like a beaker/flask). If prompted, choose **pytest** as
   the test framework and `tests` as the folder. Click the ▶ button next to
   any test or "Run Tests" at the top to run them all.

Editing `.env` is just opening it as a normal file in VS Code and typing
your values in — no terminal involved there either.

## Adding new jobs after the first sync

Whenever you save more jobs on Handshake, repeat Steps 1-2 with a fresh
paste — only genuinely new jobs get added.

## Limitations

- **No login automation.** This project deliberately does not log into your
  Handshake account programmatically, since that would violate Handshake's
  terms of service. You paste the text yourself; everything downstream is
  automated.
- **Parser is heuristic**, tuned to Handshake's current saved-jobs page
  layout. It has been tested against real Handshake exports (see
  `tests/test_parser.py`) but may need small regex tweaks if Handshake
  changes its page structure.
- **Fit scoring is keyword overlap on the job *title* only**, since
  Handshake's list view doesn't expose full descriptions. For real
  descriptions, paste them into the Notion "Notes" column and pass that
  text to `score`, or see the upgrade path below.

## Roadmap / Upgrade ideas

- Swap `resume_matcher.py`'s keyword overlap for a semantic comparison
  via the Claude API (`claude-sonnet-4-6` or later) — pass the resume and
  full job description and ask for a structured fit score + rationale.
- Extend the parser to optionally visit each job's Handshake detail page
  (still under the user's own authenticated browser session, run manually
  — not headless credential automation) to capture the full description.
- Add a GitHub Actions workflow to run `score` automatically whenever
  `jobs.json` changes, writing the result back to Notion via the API.
- Read Status changes back out of Notion to auto-generate a weekly
  application-progress summary.

## License

MIT — see [LICENSE](LICENSE).
