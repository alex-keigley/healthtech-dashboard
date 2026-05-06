"""Entity resolution helpers.

Two jobs:

1. Given a set of known companies (id, display name, canonical name),
   build a matcher that can scan free text (news article titles, summaries)
   and return which companies are mentioned. Used to attach news articles
   to existing companies in the repo.

2. Provide fuzzy-name similarity for proposing merges between records
   collected from different sources.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

from pipeline.db import canonicalize_name


# Common generic words we don't want to match on alone (too-short canonical names
# are also rejected). "health" by itself would match too much news.
_TOO_GENERIC = {
    "health", "healthcare", "medical", "bio", "pharma", "therapeutics",
    "clinical", "care", "life", "labs", "diagnostics", "medicine",
}


def _is_good_match_name(canonical: str) -> bool:
    """Decide whether a canonical name is distinctive enough to match on."""
    if not canonical:
        return False
    if len(canonical) < 6:
        return False
    words = canonical.split()
    if not words:
        return False
    if len(words) == 1 and words[0] in _TOO_GENERIC:
        return False
    # At least one word > 3 chars and not in the too-generic list
    return any(len(w) > 3 and w not in _TOO_GENERIC for w in words)


def build_company_matcher(
    companies: list[tuple[int, str, str]],
) -> list[tuple[int, str, re.Pattern]]:
    """Compile a per-company regex from canonical names.

    Returns list of (company_id, display_name, pattern).
    """
    out: list[tuple[int, str, re.Pattern]] = []
    for company_id, display, canonical in companies:
        if not _is_good_match_name(canonical):
            continue
        # Build a regex: canonical words in order with \W+ between them, so
        # names with punctuation (e.g. "Hims & Hers Health") still match when
        # the raw article text uses the original form.
        words = canonical.split()
        pattern = r"\b" + r"\W+".join(re.escape(w) for w in words) + r"\b"
        out.append((company_id, display, re.compile(pattern, re.I)))
    return out


def find_mentions(
    text: str, matcher: list[tuple[int, str, re.Pattern]]
) -> list[int]:
    """Return company_ids whose names appear in the text."""
    if not text:
        return []
    return [cid for cid, _display, pat in matcher if pat.search(text)]


def similarity(a: str, b: str) -> float:
    """Name similarity in [0, 1] using canonicalized tokens."""
    ca = canonicalize_name(a)
    cb = canonicalize_name(b)
    if not ca or not cb:
        return 0.0
    return SequenceMatcher(None, ca, cb).ratio()
