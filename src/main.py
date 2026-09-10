"""
main.py

CLI entry point for the Job Application Tracker pipeline.

Usage:
    # 1. Parse raw Handshake text (copy-pasted from your saved jobs page)
    #    into a reviewable JSON file. Nothing touches Notion at this step.
    python src/main.py parse --input raw_handshake.txt --output jobs.json

    # 2. Push new jobs into your Notion database. Existing (title, company)
    #    rows are skipped automatically -- safe to re-run on updated pastes.
    python src/main.py sync --input jobs.json

    #    Preview what would be created without writing to Notion:
    python src/main.py sync --input jobs.json --dry-run

    # 3. (Optional) Score how well your resume matches each job's title,
    #    or a job description you've pasted into job_text.txt.
    python src/main.py score --resume resume.txt --job job_description.txt
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from parser import parse_raw_text, jobs_to_dicts
from resume_matcher import score_fit


def cmd_parse(args):
    raw_text = Path(args.input).read_text(encoding="utf-8")
    jobs = jobs_to_dicts(parse_raw_text(raw_text))
    Path(args.output).write_text(json.dumps(jobs, indent=2), encoding="utf-8")
    print(f"Parsed {len(jobs)} unique jobs -> {args.output}")
    print("Review this file before syncing -- fix any mis-parsed rows by hand.")


def cmd_sync(args):
    from dotenv import load_dotenv
    load_dotenv()
    from notion_sync import NotionSync

    jobs = json.loads(Path(args.input).read_text(encoding="utf-8"))
    syncer = NotionSync()
    summary = syncer.push_jobs(jobs, dry_run=args.dry_run)

    print(f"Created: {summary['created']}  Skipped (already existed): {summary['skipped']}")
    if summary["errors"]:
        print(f"Errors ({len(summary['errors'])}):")
        for err in summary["errors"]:
            print(f"  - {err}")


def cmd_score(args):
    resume_text = Path(args.resume).read_text(encoding="utf-8")
    job_text = Path(args.job).read_text(encoding="utf-8")
    print(f"Fit score: {score_fit(resume_text, job_text)}%")
    print("Note: this is keyword overlap, not a prediction of employer response.")


def main():
    parser = argparse.ArgumentParser(description="Job Application Tracker CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_parse = sub.add_parser("parse", help="Parse raw Handshake text into JSON")
    p_parse.add_argument("--input", required=True, help="Path to raw pasted text file")
    p_parse.add_argument("--output", default="jobs.json", help="Where to write parsed JSON")
    p_parse.set_defaults(func=cmd_parse)

    p_sync = sub.add_parser("sync", help="Push parsed jobs into Notion")
    p_sync.add_argument("--input", required=True, help="Path to parsed jobs JSON")
    p_sync.add_argument("--dry-run", action="store_true", help="Preview without writing to Notion")
    p_sync.set_defaults(func=cmd_sync)

    p_score = sub.add_parser("score", help="Score resume fit against a job description")
    p_score.add_argument("--resume", required=True, help="Path to your resume as plain text")
    p_score.add_argument("--job", required=True, help="Path to job title/description as plain text")
    p_score.set_defaults(func=cmd_score)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
