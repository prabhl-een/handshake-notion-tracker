"""
parser.py

Parses raw text copy-pasted from a Handshake "Saved Jobs" page into a
list of structured job dictionaries.

Handshake's saved-jobs page renders each job card as a repeating block
of lines, roughly:

    <Company>
    <Job Title>
    <Pay> · <Type> · <Optional Date Range>
    [<Collection tag, e.g. "UCSC collection">]        (optional)
    <Location> · Apply by <Month Day, Year> at <Time>
    [blank line]
    <Apply | Quick apply | Apply externally>

This module anchors on the "Apply by ..." line (which is the most
reliable, uniquely-shaped line in the block) and walks backward to
recover the company, title, pay, and location fields. It also strips
out the site-wide navigation boilerplate that gets pulled in when you
select-and-copy a whole page (e.g. "Skip to content", "Home", "Jobs",
pagination strings like "12345 7").

This is a heuristic, best-effort parser tuned to Handshake's current
layout as of testing. If Handshake changes its page layout, or if you
paste from a different school's Handshake instance with extra fields,
you may need to adjust NAV_BOILERPLATE or the regexes below.
"""

import re
from datetime import datetime
from dataclasses import dataclass, asdict, field
from typing import Optional


APPLY_BY_RE = re.compile(
    r"Apply by (?P<date>[A-Za-z]+ \d{1,2}, \d{4}) at (?P<time>[\d:]+ ?[APMapm]{2})"
)

# A pay/type line always starts with a dollar amount, a dollar range,
# or "Unpaid", and contains a "·" separating pay / employment type / dates.
PAY_LINE_RE = re.compile(r"^(\$[\d,.KkMm+\-/a-zA-Z]*|Unpaid)\b")

# Lines that are site chrome, not job data. Extend this list if your
# school's Handshake nav differs.
NAV_BOILERPLATE = {
    "skip to content", "home", "jobs", "career center", "inbox",
    "events", "people", "employers", "feed", "ai showcase",
    "get the app", "saved", "sort by", "saved most recently",
    "newest jobs", "oldest jobs", "loading", "quick apply", "apply",
    "apply externally", "be an early applicant",
}


@dataclass
class Job:
    title: str
    company: str
    deadline: Optional[str] = None  # ISO YYYY-MM-DD
    pay: Optional[str] = None
    employment_type: Optional[str] = None
    location: Optional[str] = None
    application_mode: Optional[str] = None  # Apply / Quick apply / Apply externally
    handshake_url: Optional[str] = None

    def key(self):
        """Dedup key: title+company, case-insensitive."""
        return (self.title.strip().lower(), self.company.strip().lower())


def _is_boilerplate(line: str) -> bool:
    stripped = line.strip().lower()
    if not stripped:
        return True
    if stripped in NAV_BOILERPLATE:
        return True
    # Pagination rows like "12345 7" or "1 34567" or a lone page-size counter
    if re.fullmatch(r"[\d\s]+", stripped):
        return True
    # "37PG" style header counters, "69 saved jobs" summary lines, etc.
    if re.fullmatch(r"\d+pg", stripped):
        return True
    if re.fullmatch(r"\d+ saved jobs?", stripped):
        return True
    if re.fullmatch(r"\d+ saved jobs?", stripped):
        return True
    return False


def _parse_deadline(date_str: str) -> Optional[str]:
    try:
        return datetime.strptime(date_str, "%B %d, %Y").date().isoformat()
    except ValueError:
        return None


def parse_raw_text(raw_text: str) -> list:
    """
    Parse raw Handshake saved-jobs text into a deduplicated list of
    Job objects, sorted by deadline ascending (jobs with no parseable
    deadline are sorted last).
    """
    lines = raw_text.splitlines()
    jobs = {}

    for i, line in enumerate(lines):
        match = APPLY_BY_RE.search(line)
        if not match:
            continue

        deadline_iso = _parse_deadline(match.group("date"))
        location_part = line.split("· Apply by")[0].strip()
        # Strip a trailing "+N" (e.g. "Santa Cruz, CA + 24") if present;
        # keep it, it's genuinely useful info, just don't choke on it.
        location = location_part if location_part else None

        # Walk backward to find pay line, skipping an optional collection tag.
        pay_line = None
        j = i - 1
        skipped_collection_tag = False
        while j >= 0:
            candidate = lines[j].strip()
            if _is_boilerplate(candidate):
                j -= 1
                continue
            if PAY_LINE_RE.match(candidate):
                pay_line = candidate
                break
            # One non-boilerplate, non-pay line before we hit pay = collection tag
            if not skipped_collection_tag:
                skipped_collection_tag = True
                j -= 1
                continue
            break

        if pay_line is None:
            continue  # couldn't anchor a pay line; skip this block

        pay_parts = [p.strip() for p in pay_line.split("·")]
        pay = pay_parts[0] if pay_parts else None
        employment_type = pay_parts[1] if len(pay_parts) > 1 else None

        # Title is the next non-boilerplate line above the pay line.
        title = None
        k = j - 1
        while k >= 0:
            candidate = lines[k].strip()
            if not _is_boilerplate(candidate):
                title = candidate
                break
            k -= 1
        if title is None:
            continue

        # Company is the next non-boilerplate line above the title.
        company = None
        m = k - 1
        while m >= 0:
            candidate = lines[m].strip()
            if not _is_boilerplate(candidate):
                company = candidate
                break
            m -= 1
        if company is None:
            continue

        # Look a few lines ahead for the application mode.
        application_mode = None
        for f in range(i + 1, min(i + 5, len(lines))):
            candidate = lines[f].strip().lower()
            if candidate in ("apply", "quick apply", "apply externally"):
                application_mode = lines[f].strip()
                break

        job = Job(
            title=title,
            company=company,
            deadline=deadline_iso,
            pay=pay,
            employment_type=employment_type,
            location=location,
            application_mode=application_mode,
        )
        jobs[job.key()] = job  # overwrite duplicates, keep latest-seen

    result = list(jobs.values())
    result.sort(key=lambda j: (j.deadline is None, j.deadline or ""))
    return result


def jobs_to_dicts(jobs: list) -> list:
    return [asdict(j) for j in jobs]


if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) != 2:
        print("Usage: python parser.py <raw_text_file>")
        sys.exit(1)

    with open(sys.argv[1], "r", encoding="utf-8") as f:
        text = f.read()

    parsed = parse_raw_text(text)
    print(json.dumps(jobs_to_dicts(parsed), indent=2))
    print(f"\nParsed {len(parsed)} unique jobs.", file=sys.stderr)
