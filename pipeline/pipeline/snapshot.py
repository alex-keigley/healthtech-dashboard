"""Weekly snapshot computation.

Given a week window (start inclusive, end inclusive), compute:
  - new_founded_count: companies incorporated in the current year AND filing within window
  - new_funded_count: filings with filing_date in window
  - new_surfaced_count: companies with first_surfaced_at falling in window
  - top technology categories among window filers
  - top states among window filers
  - representative filings (biggest raises + most-tagged)

Persist the counts to `weekly_snapshots`. 1.0 change: no markdown report is
written (no `reports/` dir, nothing committed to git) — the web app renders
this data directly from the database.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime, timezone


@dataclass
class Snapshot:
    week_start: date
    week_end: date
    new_founded_count: int = 0
    new_funded_count: int = 0
    new_surfaced_count: int = 0
    top_categories: list[tuple[str, int]] = field(default_factory=list)
    top_states: list[tuple[str, int]] = field(default_factory=list)
    largest_raises: list[dict] = field(default_factory=list)
    representative_filings: list[dict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    generated_at: str = ""


def compute(conn: sqlite3.Connection, week_start: date, week_end: date) -> Snapshot:
    """Compute a Snapshot for the given inclusive window."""
    ws_iso = week_start.isoformat()
    we_iso = week_end.isoformat()
    current_year = str(week_end.year)

    new_funded = conn.execute(
        "SELECT COUNT(*) FROM filings WHERE filing_date BETWEEN ? AND ?",
        (ws_iso, we_iso),
    ).fetchone()[0]

    # Companies incorporated this year AND with a filing in the window — a proxy
    # for "brand-new company raising for the first time this week".
    new_founded = conn.execute(
        """
        SELECT COUNT(DISTINCT c.id)
          FROM companies c
          JOIN filings f ON f.company_id = c.id
         WHERE c.year_of_inc = ?
           AND f.filing_date BETWEEN ? AND ?
        """,
        (current_year, ws_iso, we_iso),
    ).fetchone()[0]

    # first_surfaced_at is stored as an ISO timestamp; match by date prefix.
    new_surfaced = conn.execute(
        """
        SELECT COUNT(*) FROM companies
         WHERE substr(first_surfaced_at, 1, 10) BETWEEN ? AND ?
        """,
        (ws_iso, we_iso),
    ).fetchone()[0]

    top_categories = [
        (r["category"], r["n"]) for r in conn.execute(
            """
            SELECT t.category, COUNT(DISTINCT c.id) AS n
              FROM filings f
              JOIN companies c ON c.id = f.company_id
              JOIN tech_tags t ON t.company_id = c.id
             WHERE f.filing_date BETWEEN ? AND ?
             GROUP BY t.category
             ORDER BY n DESC, t.category
             LIMIT 5
            """,
            (ws_iso, we_iso),
        ).fetchall()
    ]

    top_states = [
        (r["state"], r["n"]) for r in conn.execute(
            """
            SELECT c.state, COUNT(DISTINCT c.id) AS n
              FROM filings f
              JOIN companies c ON c.id = f.company_id
             WHERE f.filing_date BETWEEN ? AND ?
               AND c.state IS NOT NULL
             GROUP BY c.state
             ORDER BY n DESC, c.state
             LIMIT 5
            """,
            (ws_iso, we_iso),
        ).fetchall()
    ]

    largest_raises = [dict(r) for r in conn.execute(
        """
        SELECT c.name_display, c.state, c.focus,
               f.filing_date, f.total_offering_amount, f.filing_url
          FROM filings f
          JOIN companies c ON c.id = f.company_id
         WHERE f.filing_date BETWEEN ? AND ?
           AND f.total_offering_amount IS NOT NULL
         ORDER BY f.total_offering_amount DESC
         LIMIT 5
        """,
        (ws_iso, we_iso),
    ).fetchall()]

    # Representative filings: pick 8 that have at least one tag, diverse by category.
    rep_rows = conn.execute(
        """
        SELECT c.id AS company_id, c.name_display, c.state, c.focus,
               f.filing_date, f.total_offering_amount, f.filing_url,
               (SELECT GROUP_CONCAT(category, ' | ') FROM tech_tags WHERE company_id = c.id) AS tags
          FROM filings f
          JOIN companies c ON c.id = f.company_id
         WHERE f.filing_date BETWEEN ? AND ?
         ORDER BY f.filing_date DESC, f.total_offering_amount DESC
        """,
        (ws_iso, we_iso),
    ).fetchall()
    rep = []
    seen_cats: set[str] = set()
    for row in rep_rows:
        tags = (row["tags"] or "").split(" | ") if row["tags"] else []
        primary = tags[0] if tags else "(untagged)"
        # prefer diversity: include a filing whose primary tag hasn't appeared yet
        if primary in seen_cats and len(rep) >= 4:
            continue
        rep.append(dict(row))
        seen_cats.add(primary)
        if len(rep) >= 8:
            break

    return Snapshot(
        week_start=week_start,
        week_end=week_end,
        new_founded_count=new_founded,
        new_funded_count=new_funded,
        new_surfaced_count=new_surfaced,
        top_categories=top_categories,
        top_states=top_states,
        largest_raises=largest_raises,
        representative_filings=rep,
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


def persist(conn: sqlite3.Connection, snap: Snapshot) -> None:
    """Upsert the snapshot row in weekly_snapshots."""
    conn.execute(
        """
        INSERT INTO weekly_snapshots (week_start, new_founded_count, new_funded_count,
                                      new_surfaced_count, notes, generated_at)
             VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(week_start) DO UPDATE SET
            new_founded_count = excluded.new_founded_count,
            new_funded_count = excluded.new_funded_count,
            new_surfaced_count = excluded.new_surfaced_count,
            notes = excluded.notes,
            generated_at = excluded.generated_at
        """,
        (snap.week_start.isoformat(), snap.new_founded_count, snap.new_funded_count,
         snap.new_surfaced_count, "\n".join(snap.notes) or None, snap.generated_at),
    )
