import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from parser import parse_raw_text, Job


SAMPLE = """
UCSC Baskin Engineering
Undergraduate Research Assistant
$20/hr · On campus · Sep 2—Dec 30
UCSC collection
Santa Cruz, CA · Apply by October 3, 2026 at 11:59 PM

Quick apply


Protocolnine
Software Engineer Intern
$20-30/hr · Internship
San Jose, CA · Apply by September 18, 2026 at 11:59 PM

Apply
"""


def test_parses_expected_job_count():
    jobs = parse_raw_text(SAMPLE)
    assert len(jobs) == 2


def test_extracts_title_and_company():
    jobs = parse_raw_text(SAMPLE)
    titles = {j.title for j in jobs}
    companies = {j.company for j in jobs}
    assert "Undergraduate Research Assistant" in titles
    assert "UCSC Baskin Engineering" in companies


def test_deadline_parsed_to_iso():
    jobs = parse_raw_text(SAMPLE)
    by_title = {j.title: j for j in jobs}
    assert by_title["Undergraduate Research Assistant"].deadline == "2026-10-03"
    assert by_title["Software Engineer Intern"].deadline == "2026-09-18"


def test_sorted_by_deadline_ascending():
    jobs = parse_raw_text(SAMPLE)
    deadlines = [j.deadline for j in jobs]
    assert deadlines == sorted(deadlines)


def test_deduplicates_repeated_entries():
    doubled = SAMPLE + SAMPLE
    jobs = parse_raw_text(doubled)
    assert len(jobs) == 2  # not 4


def test_handles_collection_tag_line():
    # "UCSC collection" line between pay and location must not become the title/company
    jobs = parse_raw_text(SAMPLE)
    for j in jobs:
        assert j.company != "UCSC collection"
        assert j.title != "UCSC collection"
