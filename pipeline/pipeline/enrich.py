"""Populate `companies.description` for the most newsworthy recent companies.

Run order in the weekly pipeline: after the classifier, before snapshotting.

For each of the top-N companies funded in the lookback window we want a
short, human-readable answer to "what does this company offer?" — the
single most useful field on the dashboard for a healthcare-IT audience.

Source priority:
  1. The most recent attached news article's summary (free, already scraped
     via the RSS step, and almost always written in human-friendly prose).
  2. A meta description scraped from the company's website (resolved via
     Mojeek). Adds latency, so we only fall back here when news is missing
     AND the company looks important enough to be worth showing.
  3. Nothing — the dashboard then falls back to the heuristic focus label.

Companies that already have a cached description are skipped, so re-runs
are cheap. To force a refresh, clear companies.description directly (a
reviewer edit is preserved automatically — see db.upsert_description, which
checks the revisions table before writing).
"""

from __future__ import annotations

import time
from datetime import date
from typing import Iterable

from collectors import web_about
from pipeline import db


def _top_recent_companies(conn, since: date, limit: int) -> Iterable[dict]:
    """Top-N companies funded since `since`, ranked by largest raise."""
    rows = conn.execute(
        """
        SELECT c.id, c.name_display, c.state, c.industry_group, c.focus,
               MAX(f.total_offering_amount) AS largest_raise
          FROM companies c
          JOIN filings f ON f.company_id = c.id
         WHERE f.filing_date >= ?
         GROUP BY c.id
         ORDER BY largest_raise DESC, c.name_display
         LIMIT ?
        """,
        (since.isoformat(), limit),
    ).fetchall()
    return [dict(r) for r in rows]


def _most_recent_news(conn, company_id: int) -> dict | None:
    row = conn.execute(
        """
        SELECT url, summary
          FROM articles
         WHERE company_id = ?
           AND summary IS NOT NULL
           AND TRIM(summary) != ''
         ORDER BY published_at DESC
         LIMIT 1
        """,
        (company_id,),
    ).fetchone()
    return dict(row) if row else None


def _has_description(conn, company_id: int) -> bool:
    row = conn.execute(
        "SELECT 1 FROM companies WHERE id = ? AND description IS NOT NULL "
        "AND TRIM(description) != ''",
        (company_id,),
    ).fetchone()
    return row is not None


def enrich_top_recent(
    conn,
    *,
    since: date,
    limit: int = 15,
    delay: float = 1.5,
    now_iso: str,
    allow_web: bool = True,
) -> tuple[int, int, int, int]:
    """Ensure top-N recently-funded companies have a description cached.

    Returns (scanned, from_news, from_web, skipped_existing).
    """
    rows = _top_recent_companies(conn, since=since, limit=limit)

    scanned = 0
    from_news = 0
    from_web = 0
    skipped = 0

    for r in rows:
        scanned += 1
        cid = r["id"]
        if _has_description(conn, cid):
            skipped += 1
            continue

        news = _most_recent_news(conn, cid)
        if news:
            summary = news["summary"].strip()
            if len(summary) > 500:
                summary = summary[:499].rstrip() + "…"
            db.upsert_description(
                conn,
                company_id=cid,
                description=summary,
                url=news["url"],
                source="news",
                fetched_at=now_iso,
            )
            from_news += 1
            continue

        if not allow_web:
            continue

        try:
            info = web_about.lookup(r["name_display"], delay=delay)
        except Exception as e:  # pragma: no cover - defensive, network path
            print(f"[enrich] web lookup failed for {r['name_display']!r}: {e}")
            info = None
        if info:
            db.upsert_description(
                conn,
                company_id=cid,
                description=info.description,
                url=info.url,
                source="web",
                fetched_at=now_iso,
            )
            from_web += 1
        # Politeness pause even on miss so we don't hammer the search engine.
        time.sleep(delay)

    return scanned, from_news, from_web, skipped
