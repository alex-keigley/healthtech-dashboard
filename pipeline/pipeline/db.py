"""SQLite store for the healthtech startup repository.

1.0 schema: companies, filings, articles, tech_tags, name_aliases,
weekly_snapshots, plus the review-workflow additions (users, sessions,
otp_codes, review_items, revisions, pipeline_runs, site_settings). The
single source of truth for the schema is db/migrations/*.sql at the repo
root — this module applies those files itself (same `_migrations` bookkeeping
convention as web/scripts/migrate.mjs) so the pipeline can run standalone,
before the web app has ever started.

The DB file lives at DATABASE_PATH (env), defaulting to ../data/app.db
resolved relative to this file's repo root (i.e. `data/app.db` at the repo
root when cwd is the `pipeline/` package dir, per the documented
`cd pipeline && python -m pipeline.run` entry point).
"""

from __future__ import annotations

import os
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable, Iterator, Optional

# pipeline/pipeline/db.py -> parent is pipeline/pipeline, parent.parent is
# pipeline/ (the package dir), parent.parent.parent is the repo root.
_THIS_FILE = Path(__file__).resolve()
PACKAGE_DIR = _THIS_FILE.parent.parent          # .../pipeline
REPO_ROOT = PACKAGE_DIR.parent                  # repo root
MIGRATIONS_DIR = REPO_ROOT / "db" / "migrations"


def _default_db_path() -> Path:
    """Resolve the DB path when DATABASE_PATH isn't set.

    Walk up from this file to the repo root and use data/app.db there,
    regardless of the process cwd — robust whether invoked as
    `cd pipeline && python -m pipeline.run` (the documented way) or from
    the repo root directly.
    """
    return REPO_ROOT / "data" / "app.db"


def _resolve_db_path() -> Path:
    raw = os.environ.get("DATABASE_PATH")
    if not raw:
        return _default_db_path()
    p = Path(raw)
    if p.is_absolute():
        return p
    # Relative paths resolve from cwd, matching the web app's convention
    # (web/scripts/migrate.mjs resolves "./data/app.db" relative to its own
    # root). We mirror that: relative to the current working directory.
    return Path.cwd() / p


DB_PATH = _resolve_db_path()


_SUFFIX_RE = re.compile(
    r"\b(inc|incorporated|llc|l\.l\.c|ltd|limited|corp|corporation|co|company|lp|l\.p|llp|pllc|pc|plc)\.?\b",
    flags=re.IGNORECASE,
)
_PUNCT_RE = re.compile(r"[^\w\s]")
_WS_RE = re.compile(r"\s+")


def canonicalize_name(name: str) -> str:
    """Normalize a company name for entity resolution."""
    if not name:
        return ""
    s = name.lower()
    s = _SUFFIX_RE.sub("", s)
    s = _PUNCT_RE.sub(" ", s)
    s = _WS_RE.sub(" ", s).strip()
    return s


def _apply_migrations(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS _migrations (
            name TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
        """
    )
    if not MIGRATIONS_DIR.exists():
        return
    applied = {r[0] for r in conn.execute("SELECT name FROM _migrations").fetchall()}
    files = sorted(p for p in MIGRATIONS_DIR.glob("*.sql"))
    from datetime import datetime, timezone

    for f in files:
        if f.name in applied:
            continue
        sql = f.read_text(encoding="utf-8")
        conn.executescript(sql)
        conn.execute(
            "INSERT INTO _migrations (name, applied_at) VALUES (?, ?)",
            (f.name, datetime.now(timezone.utc).isoformat(timespec="seconds")),
        )
        conn.commit()
        print(f"[db] applied migration: {f.name}")


@contextmanager
def connect(db_path: Path = None) -> Iterator[sqlite3.Connection]:
    path = db_path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: Path = None) -> None:
    """Ensure the schema exists by applying any unapplied migration files."""
    with connect(db_path) as conn:
        _apply_migrations(conn)


# ---------------------------------------------------------------------------
# Revisions / human-edit awareness
# ---------------------------------------------------------------------------

def has_human_edit(conn: sqlite3.Connection, *, entity_type: str,
                   entity_id: int, field: str) -> bool:
    """True if a human (user_id NOT NULL) has an 'edit' revision for this field.

    The pipeline must never overwrite a field a reviewer has hand-edited —
    this is the fail-closed guard checked before every company field update.
    """
    row = conn.execute(
        """
        SELECT 1 FROM revisions
         WHERE entity_type = ? AND entity_id = ? AND field = ?
           AND action = 'edit' AND user_id IS NOT NULL
         LIMIT 1
        """,
        (entity_type, entity_id, field),
    ).fetchone()
    return row is not None


def log_revision(conn: sqlite3.Connection, *, entity_type: str, entity_id: int,
                 action: str, field: Optional[str], old_value,
                 new_value, user_id: Optional[int], created_at: str) -> None:
    conn.execute(
        """
        INSERT INTO revisions (entity_type, entity_id, action, field, old_value,
                               new_value, user_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (entity_type, entity_id, action, field,
         None if old_value is None else str(old_value),
         None if new_value is None else str(new_value),
         user_id, created_at),
    )


# ---------------------------------------------------------------------------
# Companies
# ---------------------------------------------------------------------------

# Fields the pipeline may attempt to update on an existing company. Each is
# individually gated by has_human_edit() so a reviewer's edit to, say,
# `focus` doesn't block a later machine update to `state`.
_UPDATABLE_FIELDS = (
    "cik", "state", "year_of_inc", "entity_type", "industry_group", "focus",
)


def upsert_company(conn: sqlite3.Connection, *, name: str, cik: Optional[str],
                   state: Optional[str], year_of_inc: Optional[str],
                   entity_type: Optional[str], industry_group: Optional[str],
                   focus: Optional[str], observed_at: str,
                   funded_at: Optional[str]) -> tuple[int, bool]:
    """Insert a new company (status='pending_review', the schema default) or
    update fields on an existing one, skipping any field a human has edited.

    Returns (company_id, created) where created=True means this is a brand
    new row (caller should raise a 'new_record' review item).
    """
    canonical = canonicalize_name(name)
    if not canonical:
        raise ValueError(f"Empty canonical name for input: {name!r}")

    row = conn.execute(
        "SELECT id, first_surfaced_at, first_funded_at FROM companies WHERE name_canonical = ?",
        (canonical,),
    ).fetchone()

    if row is None:
        conn.execute(
            """
            INSERT INTO companies (
                name_canonical, name_display, cik, state, year_of_inc, entity_type,
                industry_group, focus, first_surfaced_at, first_funded_at,
                last_updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (canonical, name, cik, state, year_of_inc, entity_type, industry_group,
             focus, observed_at, funded_at, observed_at),
        )
        company_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        log_revision(
            conn, entity_type="company", entity_id=company_id, action="create",
            field=None, old_value=None, new_value=name, user_id=None,
            created_at=observed_at,
        )
        return company_id, True

    company_id = row["id"]

    # Fetch current values so COALESCE-style "fill if empty" logic still
    # applies, but never touch a field a human has hand-edited.
    current = conn.execute(
        "SELECT cik, state, year_of_inc, entity_type, industry_group, focus, "
        "first_funded_at FROM companies WHERE id = ?",
        (company_id,),
    ).fetchone()

    candidate_values = {
        "cik": cik,
        "state": state,
        "year_of_inc": year_of_inc,
        "entity_type": entity_type,
        "industry_group": industry_group,
        "focus": focus,
    }
    set_clauses = []
    params: list = []
    for field in _UPDATABLE_FIELDS:
        if has_human_edit(conn, entity_type="company", entity_id=company_id, field=field):
            continue  # never overwrite a human edit
        new_val = candidate_values[field]
        cur_val = current[field]
        if field == "focus":
            # POC semantics: prefer the new value if given, else keep current.
            resolved = new_val if new_val else cur_val
        else:
            # POC semantics: fill only if currently empty.
            resolved = cur_val if cur_val else new_val
        set_clauses.append(f"{field} = ?")
        params.append(resolved)

    existing_funded = current["first_funded_at"]
    earliest_funded = (
        min(d for d in [existing_funded, funded_at] if d)
        if (existing_funded or funded_at) else None
    )
    set_clauses.append("first_funded_at = ?")
    params.append(earliest_funded)
    set_clauses.append("last_updated_at = ?")
    params.append(observed_at)

    params.append(company_id)
    conn.execute(
        f"UPDATE companies SET {', '.join(set_clauses)} WHERE id = ?",
        params,
    )
    return company_id, False


def get_company(conn: sqlite3.Connection, company_id: int) -> Optional[sqlite3.Row]:
    return conn.execute("SELECT * FROM companies WHERE id = ?", (company_id,)).fetchone()


def set_company_status(conn: sqlite3.Connection, company_id: int, status: str) -> None:
    conn.execute("UPDATE companies SET status = ? WHERE id = ?", (status, company_id))


# ---------------------------------------------------------------------------
# Filings / articles
# ---------------------------------------------------------------------------

def upsert_filing(conn: sqlite3.Connection, *, accession: str, company_id: int,
                  source: str, filing_date: Optional[str],
                  date_of_first_sale: Optional[str],
                  total_offering_amount: Optional[float],
                  filing_url: Optional[str], observed_at: str) -> None:
    conn.execute(
        """
        INSERT INTO filings (
            accession, company_id, source, filing_date, date_of_first_sale,
            total_offering_amount, filing_url, observed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(accession) DO UPDATE SET
            filing_date = excluded.filing_date,
            date_of_first_sale = excluded.date_of_first_sale,
            total_offering_amount = excluded.total_offering_amount,
            filing_url = excluded.filing_url
        """,
        (accession, company_id, source, filing_date, date_of_first_sale,
         total_offering_amount, filing_url, observed_at),
    )


def upsert_article(conn: sqlite3.Connection, *, company_id: int, source: str,
                   title: str, url: str, summary: Optional[str],
                   published_at: Optional[str], observed_at: str) -> None:
    conn.execute(
        """
        INSERT INTO articles (company_id, source, title, url, summary, published_at, observed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(url) DO UPDATE SET
            title = excluded.title,
            summary = excluded.summary,
            published_at = excluded.published_at
        """,
        (company_id, source, title, url, summary, published_at, observed_at),
    )


def upsert_description(conn: sqlite3.Connection, *, company_id: int,
                       description: str, url: Optional[str], source: str,
                       fetched_at: str) -> None:
    """Set companies.description/description_source/description_url.

    `source` is one of: "news" (copied from a recent attached article),
    "web" (meta-description scraped from the company's site). Skips the
    write if a human has hand-edited the description field.
    """
    if has_human_edit(conn, entity_type="company", entity_id=company_id, field="description"):
        return
    conn.execute(
        """
        UPDATE companies
           SET description = ?,
               description_source = ?,
               description_url = ?,
               last_updated_at = ?
         WHERE id = ?
        """,
        (description, source, url, fetched_at, company_id),
    )


# ---------------------------------------------------------------------------
# Tech tags (origin-aware: machine vs human)
# ---------------------------------------------------------------------------

def replace_machine_tags(conn: sqlite3.Connection, *, company_id: int,
                         tags: list[tuple[str, float]], tagged_at: str) -> None:
    """Replace machine-origin tags for this company with the given set.

    Never touches origin='human' rows: if a human has tagged a category,
    the classifier's write to that category is skipped entirely (both on
    delete and on insert), so a human tag can't be clobbered or masked.
    """
    human_categories = {
        r["category"] for r in conn.execute(
            "SELECT category FROM tech_tags WHERE company_id = ? AND origin = 'human'",
            (company_id,),
        ).fetchall()
    }
    conn.execute(
        "DELETE FROM tech_tags WHERE company_id = ? AND origin = 'machine'",
        (company_id,),
    )
    for category, confidence in tags:
        if category in human_categories:
            continue
        conn.execute(
            """
            INSERT INTO tech_tags (company_id, category, confidence, origin, tagged_at)
            VALUES (?, ?, ?, 'machine', ?)
            ON CONFLICT(company_id, category) DO UPDATE SET
                confidence = excluded.confidence,
                tagged_at = excluded.tagged_at
            WHERE tech_tags.origin = 'machine'
            """,
            (company_id, category, confidence, tagged_at),
        )


# ---------------------------------------------------------------------------
# Review items
# ---------------------------------------------------------------------------

def add_review_item(conn: sqlite3.Connection, *, type_: str,
                    company_id: Optional[int] = None,
                    other_company_id: Optional[int] = None,
                    payload: Optional[str] = None, created_at: str) -> None:
    """INSERT OR IGNORE respecting UNIQUE(type, company_id, other_company_id)."""
    conn.execute(
        """
        INSERT OR IGNORE INTO review_items
            (type, company_id, other_company_id, payload, state, created_at)
        VALUES (?, ?, ?, ?, 'open', ?)
        """,
        (type_, company_id, other_company_id, payload, created_at),
    )


def has_open_review_item(conn: sqlite3.Connection, *, type_: str,
                         company_id: Optional[int],
                         other_company_id: Optional[int] = None) -> bool:
    row = conn.execute(
        """
        SELECT 1 FROM review_items
         WHERE type = ? AND company_id IS ? AND other_company_id IS ?
           AND state = 'open'
         LIMIT 1
        """,
        (type_, company_id, other_company_id),
    ).fetchone()
    return row is not None


# ---------------------------------------------------------------------------
# Pipeline runs
# ---------------------------------------------------------------------------

def start_run(conn: sqlite3.Connection, *, started_at: str,
             window_start: Optional[str], window_end: Optional[str]) -> int:
    conn.execute(
        """
        INSERT INTO pipeline_runs (started_at, window_start, window_end, status)
        VALUES (?, ?, ?, 'running')
        """,
        (started_at, window_start, window_end),
    )
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def finish_run(conn: sqlite3.Connection, *, run_id: int, finished_at: str,
              status: str, stats: str, qa_findings: str) -> None:
    conn.execute(
        """
        UPDATE pipeline_runs
           SET finished_at = ?, status = ?, stats = ?, qa_findings = ?
         WHERE id = ?
        """,
        (finished_at, status, stats, qa_findings, run_id),
    )


# ---------------------------------------------------------------------------
# Query helpers used by classifier / entity_resolver / enrich / snapshot / review
# ---------------------------------------------------------------------------

def all_companies_with_text(conn: sqlite3.Connection) -> Iterable[sqlite3.Row]:
    """Return every company with concatenated text used for classification."""
    return conn.execute(
        """
        SELECT c.id, c.name_display, c.industry_group, c.focus, c.status,
               GROUP_CONCAT(a.title, ' . ') AS article_titles,
               GROUP_CONCAT(a.summary, ' . ') AS article_summaries
          FROM companies c
          LEFT JOIN articles a ON a.company_id = c.id
      GROUP BY c.id
        """
    ).fetchall()


def all_company_names(conn: sqlite3.Connection) -> list[tuple[int, str, str]]:
    """Return (id, display_name, canonical_name) for every known company."""
    rows = conn.execute("SELECT id, name_display, name_canonical FROM companies").fetchall()
    return [(r["id"], r["name_display"], r["name_canonical"]) for r in rows]


def fetch_recent_filings(conn: sqlite3.Connection, limit: int = 100) -> Iterable[sqlite3.Row]:
    return conn.execute(
        """
        SELECT c.name_display, c.state, c.industry_group, c.entity_type,
               f.filing_date, f.total_offering_amount, f.filing_url, f.accession
          FROM filings f
          JOIN companies c ON c.id = f.company_id
         ORDER BY f.filing_date DESC, f.accession DESC
         LIMIT ?
        """,
        (limit,),
    ).fetchall()


if __name__ == "__main__":
    init_db()
    print(f"Initialized {DB_PATH}")
