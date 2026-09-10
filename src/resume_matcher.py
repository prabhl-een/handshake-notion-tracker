"""
resume_matcher.py

A free, no-API-key resume-to-job fit scorer based on keyword overlap,
with a few improvements over naive exact-string matching:

  - Lightweight stemming, so "engineering"/"engineer"/"engineers" (or
    "internship"/"intern") count as the same word instead of requiring
    an exact match.
  - A small synonym map for common abbreviations (SWE, UX, ML, etc.)
    that mean the same thing as their spelled-out forms.
  - A noise-word list that filters out job-posting boilerplate
    ("candidate", "opportunity", "position", etc.) that isn't a real
    skill signal and was previously counting against every job equally,
    since resumes don't typically contain that kind of phrasing.
  - A softening curve on the final score, since raw keyword overlap on
    SHORT text (often just a job title, since full descriptions aren't
    available -- see the note below) punishes a single missing word
    very harshly. The curve gives meaningful partial credit instead of
    an all-or-nothing cliff.
  - An experience-level check: jobs signaling a seniority bar (Senior,
    Director, advanced degree, 3+ years required) that the resume
    doesn't back up get capped low regardless of topical overlap, while
    generic/entry-level jobs get a baseline floor, since those are
    realistically attainable for a student regardless of exact wording
    overlap with their resume.

IMPORTANT LIMITATION (unchanged): Handshake's saved-jobs list view only
exposes job title, company, pay, and location -- not the full job
description. That means this scorer, on jobs without a captured
description, compares your resume against job *titles* (plus pay/type/
location) only, which is inherently a weaker signal than a real
description would give. For meaningful scores on a specific job, paste
its description into the Notion "Notes" column and pass that text to
score_fit() directly, or see the README's "Upgrading the matcher"
section for swapping this out for the Claude API.

This is still a heuristic keyword/stem overlap score, not a real
assessment of qualification, and definitely not a prediction of
whether an employer will respond. Use it to prioritize which jobs to
look at first, not as a verdict.
"""

import re

STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "is", "are", "was", "were", "be", "been", "being",
    "this", "that", "these", "those", "it", "as", "by", "from", "will",
    "we", "you", "your", "our", "their", "have", "has", "had", "not",
    "if", "then", "than", "so", "such", "into", "about", "up",
    "out", "who", "what", "when", "where", "why", "how", "all", "any",
    "both", "each", "few", "more", "most", "other", "some", "no",
}

# Job-posting boilerplate that shows up constantly regardless of the
# actual role, and isn't a skill/domain signal -- filtering these out
# stops them from diluting the score just because a resume (reasonably)
# doesn't contain phrases like "strong candidate" or "growth opportunity".
NOISE_WORDS = {
    "role", "team", "work", "opportunity", "opportunities", "experience",
    "environment", "company", "position", "job", "jobs", "looking",
    "candidate", "candidates", "strong", "excellent", "ability", "skills",
    "required", "preferred", "applicants", "apply", "hour", "hours",
    "hourly", "week", "weekly", "month", "monthly", "year", "yearly",
    "paid", "unpaid", "remote", "hybrid", "onsite", "campus", "student",
    "students", "full", "part", "time",
}

# Suffixes stripped (longest first) for lightweight stemming -- not
# linguistically rigorous, just enough to catch common job/resume word
# variants (engineer/engineering, intern/internship, research/researcher).
_SUFFIXES = sorted(
    ["ational", "tional", "edly", "ship", "ing", "ies", "ied", "ers",
     "ors", "es", "ed", "ly", "er", "or", "s"],
    key=len, reverse=True,
)

# Common abbreviations mapped to the words they stand for, so e.g. a
# resume that says "SWE" matches a job titled "Software Engineer Intern".
SYNONYM_MAP = {
    "swe": ["software", "engineer"],
    "js": ["javascript"],
    "ml": ["machine", "learning"],
    "ai": ["artificial", "intelligence"],
    "ux": ["user", "experience"],
    "ui": ["user", "interface"],
    "dev": ["developer"],
    "eng": ["engineer"],
    "mktg": ["marketing"],
    "comms": ["communications"],
    "mgmt": ["management"],
    "coord": ["coordinator"],
    "admin": ["administrative"],
    "hr": ["human", "resources"],
    "cs": ["computer", "science"],
    "biz": ["business"],
}


def _stem(word: str) -> str:
    for suf in _SUFFIXES:
        if word.endswith(suf) and len(word) - len(suf) >= 3:
            return word[: -len(suf)]
    return word


def _tokenize(text: str) -> set:
    raw_words = re.findall(r"[a-zA-Z][a-zA-Z+#.\-]{1,}", text.lower())
    tokens = set()
    for w in raw_words:
        w = w.strip(".-")
        if not w or w in STOPWORDS or w in NOISE_WORDS or len(w) <= 1:
            continue
        tokens.add(_stem(w))
        if w in SYNONYM_MAP:
            tokens.update(_stem(syn) for syn in SYNONYM_MAP[w])
    return tokens


# Words/patterns signaling a seniority or experience bar most early-career
# resumes won't clear, regardless of how well the topic itself matches.
HIGH_BAR_WORDS = {
    "senior", "sr", "lead", "director", "principal", "staff", "head",
    "chief", "vp", "manager", "supervisor",
}
ADVANCED_DEGREE_WORDS = {"phd", "doctorate", "mba", "md", "jd"}
_YEARS_RE = re.compile(r"\b(\d+)\+?\s*years?\b")

# Baseline for jobs that AREN'T flagged as high-bar: a student can
# realistically be considered for most generic/entry-level roles
# regardless of exact keyword overlap with their major or resume
# wording (e.g. a CS student applying to a campus cashier job isn't
# unrealistic the way applying to a "Senior Engineer" role would be).
ENTRY_LEVEL_FLOOR = 35

# Ceiling applied when a job signals a seniority/experience level (or
# advanced degree, or several years of required experience) that
# nothing in the resume backs up -- a real experience gap should matter
# more than incidental keyword overlap.
HIGH_BAR_CAP = 20


def _is_high_bar(text: str) -> bool:
    words = set(re.findall(r"[a-zA-Z]+", text.lower()))
    if words & HIGH_BAR_WORDS:
        return True
    if words & ADVANCED_DEGREE_WORDS:
        return True
    years_matches = _YEARS_RE.findall(text.lower())
    if any(int(y) >= 3 for y in years_matches):
        return True
    return False


def score_fit(resume_text: str, job_text: str) -> int:
    """
    Returns an integer 0-100. Combines two signals:

    1. Stemmed/synonym-aware keyword overlap between resume and job text
       (with a softening curve so partial matches aren't punished as
       harshly as a straight-line percentage would).
    2. An experience-level check: if the job's language signals a bar
       (seniority words, an advanced degree, 3+ years required) that the
       resume doesn't show any matching signal for, the score is capped
       low regardless of topical overlap. If the job ISN'T flagged as
       high-bar, a baseline floor applies instead, since most entry-level
       or generic roles are realistically attainable for a student
       regardless of exact wording overlap with their resume.

    This is NOT a prediction of whether you'll hear back, and the
    high-bar/entry-level check is a blunt heuristic based on job-title
    language, not a real assessment of your qualifications -- use it to
    prioritize which jobs to look at first, not as a verdict.
    """
    resume_words = _tokenize(resume_text)
    job_words = _tokenize(job_text)

    keyword_score = 0
    job_is_high_bar = _is_high_bar(job_text)

    if job_words:
        overlap = resume_words & job_words
        raw_ratio = len(overlap) / len(job_words)
        keyword_score = round(100 * (raw_ratio ** 0.5))

    if job_is_high_bar:
        # Deliberately no "does the resume also show seniority?" escape
        # hatch here -- an early check for that using HIGH_BAR_WORDS
        # against the resume produced false positives from ordinary club
        # leadership titles ("Social Media Director") and passing
        # mentions ("the lead teacher was out"), which aren't the same
        # thing as professional-level seniority. For a student job
        # tracker, always capping high-bar postings low is the safer,
        # more accurate default.
        return min(keyword_score, HIGH_BAR_CAP)

    return min(max(keyword_score, ENTRY_LEVEL_FLOOR), 100)