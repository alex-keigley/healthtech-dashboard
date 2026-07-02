"""Review queue population.

1.0 replaces the POC's review/pending.md with rows in `review_items` — a
queryable, stateful queue the reviewer tool works against instead of a
markdown file resolved via pull request.

Bias toward "hold for review" over false positives. For a healthcare-IT
audience, a single low-quality startup in the public repo costs more trust
than a few missed ones.

Types populated here:
  - untagged: classifier had no signal at all (zero tech_tags rows, of any
    origin). A reviewer either confirms the company really is non-specific
    or adds a tag manually.
  - low_confidence: a company whose best tag (any origin) is below the 0.7
    confidence bar.
  - fuzzy_match: pairs of companies with name similarity in the
    [0.75, 0.95) band. Above 0.95 is auto-merge territory (not handled
    here); below 0.75 is noise.

`new_record` items are raised inline by run.py at the moment a company row
is created (it knows the source there), not by this module.

Untagged/low_confidence items are NOT created for companies whose status is
'invalidated' or 'archived' (dead records shouldn't clutter the queue), and
duplicates of still-open items are skipped via review_items' UNIQUE
constraint + an explicit has_open_review_item guard so re-runs are cheap
and don't re-litigate a dismissed item's underlying condition every week
for no reason beyond the constraint.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from pipeline import db
from pipeline.entity_resolver import _TOO_GENERIC, similarity

_EXCLUDED_STATUSES = ("invalidated", "archived")


def _distinctive_tokens(canonical: str) -> set[str]:
    """Tokens worth identity-matching on: non-generic, longer than 2 chars."""
    if not canonical:
        return set()
    return {w for w in canonical.split() if w not in _TOO_GENERIC and len(w) > 2}


def _plausible_duplicate(a_canon: str, b_canon: str) -> bool:
    """Two names are plausibly the same company only if they share at least
    one distinctive token. `Alloy Therapeutics` vs `Bonum Therapeutics` share
    only 'therapeutics' (generic) — so they're NOT plausible duplicates even
    though SequenceMatcher rates them highly."""
    ta = _distinctive_tokens(a_canon)
    tb = _distinctive_tokens(b_canon)
    if not ta or not tb:
        return False
    return bool(ta & tb)


def _find_untagged(conn: sqlite3.Connection, limit: int = 200) -> list[dict]:
    rows = conn.execute(
        f"""
        SELECT c.id, c.name_display, c.state, c.focus, c.industry_group,
               c.first_surfaced_at,
               (SELECT MAX(f.total_offering_amount) FROM filings f WHERE f.company_id = c.id) AS largest_raise,
               (SELECT MAX(f.filing_url) FROM filings f WHERE f.company_id = c.id) AS filing_url
          FROM companies c
          LEFT JOIN tech_tags t ON t.company_id = c.id
         WHERE t.category IS NULL
           AND c.status NOT IN ({",".join("?" * len(_EXCLUDED_STATUSES))})
         ORDER BY c.last_updated_at DESC
         LIMIT ?
        """,
        (*_EXCLUDED_STATUSES, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def _find_low_confidence(conn: sqlite3.Connection,
                         threshold: float = 0.7,
                         limit: int = 200) -> list[dict]:
    rows = conn.execute(
        f"""
        SELECT c.id, c.name_display, c.state, c.focus,
               MAX(t.confidence) AS best_confidence,
               GROUP_CONCAT(t.category, ' | ') AS tags
          FROM companies c
          JOIN tech_tags t ON t.company_id = c.id
         WHERE c.status NOT IN ({",".join("?" * len(_EXCLUDED_STATUSES))})
         GROUP BY c.id
        HAVING MAX(t.confidence) < ?
         ORDER BY best_confidence ASC
         LIMIT ?
        """,
        (*_EXCLUDED_STATUSES, threshold, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def _find_fuzzy_pairs(conn: sqlite3.Connection,
                      lo: float = 0.75, hi: float = 0.95,
                      limit: int = 200) -> list[dict]:
    """Pairwise compare canonical names and surface ambiguous matches.

    O(N^2) but at this scale (tens to hundreds of companies) that's fine;
    a blocking strategy can be added if the repo grows enough to matter.
    Excludes invalidated/archived companies on either side of the pair.
    """
    rows = conn.execute(
        f"""
        SELECT id, name_display, name_canonical FROM companies
         WHERE status NOT IN ({",".join("?" * len(_EXCLUDED_STATUSES))})
         ORDER BY name_canonical
        """,
        _EXCLUDED_STATUSES,
    ).fetchall()
    out: list[dict] = []
    for i, a in enumerate(rows):
        for b in rows[i + 1:]:
            if not _plausible_duplicate(a["name_canonical"], b["name_canonical"]):
                continue
            s = similarity(a["name_canonical"], b["name_canonical"])
            if lo <= s < hi:
                out.append({
                    "a_id": a["id"],
                    "b_id": b["id"],
                    "a_name": a["name_display"],
                    "b_name": b["name_display"],
                    "similarity": round(s, 3),
                })
                if len(out) >= limit:
                    return out
    return out


def populate(conn: sqlite3.Connection) -> dict[str, int]:
    """Scan the DB and insert review_items rows. Returns counts per type.

    Idempotent: relies on INSERT OR IGNORE against the UNIQUE(type,
    company_id, other_company_id) constraint, plus an explicit
    has_open_review_item check so we don't even attempt duplicate inserts
    for conditions that already have an open item.
    """
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    counts = {"untagged": 0, "low_confidence": 0, "fuzzy_match": 0}

    for r in _find_untagged(conn):
        cid = r["id"]
        if db.has_open_review_item(conn, type_="untagged", company_id=cid):
            continue
        db.add_review_item(conn, type_="untagged", company_id=cid, created_at=now)
        counts["untagged"] += 1

    for r in _find_low_confidence(conn):
        cid = r["id"]
        if db.has_open_review_item(conn, type_="low_confidence", company_id=cid):
            continue
        payload = json.dumps({
            "best_confidence": r["best_confidence"],
            "tags": r.get("tags"),
        })
        db.add_review_item(conn, type_="low_confidence", company_id=cid,
                           payload=payload, created_at=now)
        counts["low_confidence"] += 1

    for p in _find_fuzzy_pairs(conn):
        a_id, b_id = p["a_id"], p["b_id"]
        if db.has_open_review_item(conn, type_="fuzzy_match", company_id=a_id,
                                   other_company_id=b_id):
            continue
        payload = json.dumps({
            "a_name": p["a_name"],
            "b_name": p["b_name"],
            "similarity": p["similarity"],
        })
        db.add_review_item(conn, type_="fuzzy_match", company_id=a_id,
                           other_company_id=b_id, payload=payload, created_at=now)
        counts["fuzzy_match"] += 1

    return counts
