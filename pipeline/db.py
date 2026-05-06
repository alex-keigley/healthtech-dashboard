"""SQLite store for the healthtech startup repository.

Phase 1 schema: companies, filings, weekly_snapshots. Later phases will add
tech_tags, additional source tables, and review queues.

The DB file lives at `data/startups.db` and is meant to be committed to git
so history is auditable. Streamlit reads directly from this file.
"""

from __future__ import annotations

import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable, Iterator

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "startups.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name_canonical TEXT NOT NULL UNIQUE,
    name_display TEXT NOT NULL,
    cik TEXT,
    state TEXT,
    year_of_inc TEXT,
    entity_type TEXT,
    industry_group TEXT,
    focus TEXT,
    first_surfaced_at TEXT NOT NULL,
    first_funded_at TEXT,
    last_updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS filings (
    accession TEXT PRIMARY KEY,
    company_id INTEGER NOT NULL,
    source TEXT NOT NULL,
    filing_date TEXT,
    date_of_first_sale TEXT,
    total_offering_amount REAL,
    filing_url TEXT,
    observed_at TEXT NOT NULL,
    FOREIGN KEY (company_id) REFERENCES companies(id)
);

CREATE INDEX IF NOT EXISTS idx_filings_date ON filings(filing_date);
CREATE INDEX IF NOT EXISTS idx_companies_state ON companies(state);
CREATE INDEX IF NOT EXISTS idx_companies_industry ON companies(industry_group);

CREATE TABLE IF NOT EXISTS weekly_snapshots (
    week_start TEXT PRIMARY KEY,
    new_founded_count INTEGER NOT NULL DEFAULT 0,
    new_funded_count INTEGER NOT NULL DEFAULT 0,
    new_surfaced_count INTEGER NOT NULL DEFAULT 0,
    notes TEXT,
    generated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    source TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL UNIQUE,
    summary TEXT,
    published_at TEXT,
    observed_at TEXT NOT NULL,
    FOREIGN KEY (company_id) REFERENCES companies(id)
);
CREATE INDEX IF NOT EXISTS idx_articles_company ON articles(company_id);
CREATE INDEX IF NOT EXISTS idx_articles_published ON articles(published_at);

CREATE TABLE IF NOT EXISTS tech_tags (
    company_id INTEGER NOT NULL,
    category TEXT NOT NULL,
    confidence REAL NOT NULL,
    tagged_at TEXT NOT NULL,
    PRIMARY KEY (company_id, category),
    FOREIGN KEY (company_id) REFERENCES companies(id)
);
CREATE INDEX IF NOT EXISTS idx_tech_tags_category ON tech_tags(category);

CREATE TABLE IF NOT EXISTS name_aliases (
    company_id INTEGER NOT NULL,
    alias_canonical TEXT NOT NULL,
    alias_display TEXT NOT NULL,
    source TEXT NOT NULL,
    PRIMARY KEY (company_id, alias_canonical),
    FOREIGN KEY (company_id) REFERENCES companies(id)
);

-- Cached human-readable description of "what the company offers". Populated
-- by the enrich stage with one of: a recent news article summary, a meta
-- description scraped from the company's website, or (rarely) a manual edit.
CREATE TABLE IF NOT EXISTS company_descriptions (
    company_id INTEGER PRIMARY KEY,
    description TEXT NOT NULL,
    url TEXT,
    source TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    FOREIGN KEY (company_id) REFERENCES companies(id)
);
"""


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


@contextmanager
def connect(db_path: Path = DB_PATH) -> Iterator[sqlite3.Connection]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: Path = DB_PATH) -> None:
    with connect(db_path) as conn:
        conn.executescript(SCHEMA)


def upsert_company(conn: sqlite3.Connection, *, name: str, cik: str | None,
                   state: str | None, year_of_inc: str | None, entity_type: str | None,
                   industry_group: str | None, focus: str | None, observed_at: str,
                   funded_at: str | None) -> int:
    """Insert a new company or update fields on an existing one. Returns company id."""
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
                industry_group, focus, first_surfaced_at, first_funded_at, last_updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (canonical, name, cik, state, year_of_inc, entity_type, industry_group,
             focus, observed_at, funded_at, observed_at),
        )
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    company_id = row["id"]
    existing_funded = row["first_funded_at"]
    earliest_funded = min(d for d in [existing_funded, funded_at] if d) if (existing_funded or funded_at) else None
    conn.execute(
        """
        UPDATE companies
           SET cik = COALESCE(cik, ?),
               state = COALESCE(state, ?),
               year_of_inc = COALESCE(year_of_inc, ?),
               entity_type = COALESCE(entity_type, ?),
               industry_group = COALESCE(industry_group, ?),
               focus = COALESCE(?, focus),
               first_funded_at = ?,
               last_updated_at = ?
         WHERE id = ?
        """,
        (cik, state, year_of_inc, entity_type, industry_group, focus,
         earliest_funded, observed_at, company_id),
    )
    return company_id


def upsert_filing(conn: sqlite3.Connection, *, accession: str, company_id: int,
                  source: str, filing_date: str | None,
                  date_of_first_sale: str | None, total_offering_amount: float | None,
                  filing_url: str | None, observed_at: str) -> None:
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
                   title: str, url: str, summary: str | None,
                   published_at: str | None, observed_at: str) -> None:
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
                       description: str, url: str | None, source: str,
                       fetched_at: str) -> None:
    """Cache a human-readable description for a company.

    `source` is one of: "news" (copied from a recent attached article),
    "web" (meta-description scraped from the company's site), or "manual".
    """
    conn.execute(
        """
        INSERT INTO company_descriptions (company_id, description, url, source, fetched_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(company_id) DO UPDATE SET
            description = excluded.description,
            url = excluded.url,
            source = excluded.source,
            fetched_at = excluded.fetched_at
        """,
        (company_id, description, url, source, fetched_at),
    )


def replace_tech_tags(conn: sqlite3.Connection, *, company_id: int,
                     tags: list[tuple[str, float]], tagged_at: str) -> None:
    """Remove existing tags for this company and replace with the given set."""
    conn.execute("DELETE FROM tech_tags WHERE company_id = ?", (company_id,))
    if not tags:
        return
    conn.executemany(
        "INSERT INTO tech_tags (company_id, category, confidence, tagged_at) VALUES (?, ?, ?, ?)",
        [(company_id, category, confidence, tagged_at) for category, confidence in tags],
    )


def all_companies_with_text(conn: sqlite3.Connection) -> Iterable[sqlite3.Row]:
    """Return every company with concatenated text used for classification."""
    return conn.execute(
        """
        SELECT c.id, c.name_display, c.industry_group, c.focus,
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
