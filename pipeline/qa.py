"""Automated QA gates.

Each gate inspects the current database state and returns zero or more
findings. Findings never raise — they're surfaced to the pipeline runner, which
decides whether to block the weekly commit or just warn. Gates are cheap
enough to run every pipeline tick.

Current gates:
  - check_spike: week-over-week filings count > 2σ above 12-week trailing mean
  - check_orphan_tags: fraction of companies with zero technology tags
  - check_stale_sources: a source has had 0 records for 2+ consecutive weeks
  - check_broken_urls: sample of filing URLs should return HTTP 200
"""

from __future__ import annotations

import random
import sqlite3
import statistics
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable

import requests

USER_AGENT = "Healthtech Dashboard 507webdev@gmail.com"


@dataclass
class Finding:
    gate: str
    severity: str  # "info" | "warn" | "block"
    message: str


def check_spike(conn: sqlite3.Connection, week_end: date,
                lookback_weeks: int = 12, sigma: float = 2.0) -> list[Finding]:
    """Compare this week's filing count to the trailing N-week mean."""
    buckets: list[int] = []
    for i in range(lookback_weeks + 1):
        end = week_end - timedelta(days=7 * i)
        start = end - timedelta(days=6)
        n = conn.execute(
            "SELECT COUNT(*) FROM filings WHERE filing_date BETWEEN ? AND ?",
            (start.isoformat(), end.isoformat()),
        ).fetchone()[0]
        buckets.append(n)
    this_week = buckets[0]
    history = buckets[1:]
    # Drop leading zeros (weeks before we started collecting) from history.
    while history and history[-1] == 0:
        history.pop()
    if len(history) < 3:
        return [Finding(gate="spike", severity="info",
                        message=f"Not enough history ({len(history)} weeks) for spike detection")]
    mean = statistics.mean(history)
    stdev = statistics.pstdev(history) if len(history) > 1 else 0.0
    threshold = mean + sigma * stdev
    if stdev > 0 and this_week > threshold:
        return [Finding(
            gate="spike", severity="warn",
            message=(f"Filings this week ({this_week}) exceed "
                     f"{sigma}σ over trailing {len(history)}-week mean "
                     f"({mean:.1f} ± {stdev:.1f}); threshold {threshold:.1f}")
        )]
    return [Finding(gate="spike", severity="info",
                    message=f"Filings this week ({this_week}) within expected range "
                            f"(trailing mean {mean:.1f})")]


def check_orphan_tags(conn: sqlite3.Connection,
                      threshold_fraction: float = 0.5) -> list[Finding]:
    """Flag if too many companies have zero technology tags after classification."""
    total = conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
    if total == 0:
        return []
    tagged = conn.execute(
        "SELECT COUNT(DISTINCT company_id) FROM tech_tags"
    ).fetchone()[0]
    orphans = total - tagged
    frac = orphans / total
    msg = f"{orphans}/{total} companies have no technology tag ({frac:.0%})"
    sev = "warn" if frac > threshold_fraction else "info"
    return [Finding(gate="orphan_tags", severity=sev, message=msg)]


def check_stale_sources(conn: sqlite3.Connection, week_end: date,
                        lookback_weeks: int = 2) -> list[Finding]:
    """Alert if a source has returned 0 records for N consecutive weeks."""
    findings: list[Finding] = []
    sources = [r["source"] for r in conn.execute(
        "SELECT DISTINCT source FROM filings"
    ).fetchall()]
    for src in sources:
        counts = []
        for i in range(lookback_weeks):
            end = week_end - timedelta(days=7 * i)
            start = end - timedelta(days=6)
            n = conn.execute(
                "SELECT COUNT(*) FROM filings WHERE source = ? AND filing_date BETWEEN ? AND ?",
                (src, start.isoformat(), end.isoformat()),
            ).fetchone()[0]
            counts.append(n)
        if all(c == 0 for c in counts):
            findings.append(Finding(
                gate="stale_source", severity="warn",
                message=f"Source {src!r} has 0 records for the last {lookback_weeks} weeks",
            ))
    return findings


def check_broken_urls(conn: sqlite3.Connection, sample_size: int = 10,
                      timeout: float = 10.0) -> list[Finding]:
    """HEAD-check a random sample of filing URLs to catch source breakage."""
    urls = [r[0] for r in conn.execute(
        "SELECT filing_url FROM filings WHERE filing_url IS NOT NULL"
    ).fetchall() if r[0]]
    if not urls:
        return [Finding(gate="broken_urls", severity="info",
                        message="No filing URLs available to sample")]
    sample = random.sample(urls, min(sample_size, len(urls)))
    headers = {"User-Agent": USER_AGENT}
    failures: list[str] = []
    for url in sample:
        try:
            r = requests.head(url, headers=headers, timeout=timeout, allow_redirects=True)
            if r.status_code >= 400:
                failures.append(f"{r.status_code} {url}")
        except requests.RequestException as e:
            failures.append(f"err {e.__class__.__name__} {url}")
    if failures:
        return [Finding(
            gate="broken_urls", severity="warn",
            message=(f"{len(failures)}/{len(sample)} sampled URLs failed: "
                     + "; ".join(failures[:3]) + ("…" if len(failures) > 3 else "")),
        )]
    return [Finding(gate="broken_urls", severity="info",
                    message=f"All {len(sample)} sampled URLs returned 2xx/3xx")]


def run_all(conn: sqlite3.Connection, week_end: date,
            skip_url_check: bool = False) -> list[Finding]:
    findings: list[Finding] = []
    findings.extend(check_spike(conn, week_end))
    findings.extend(check_orphan_tags(conn))
    findings.extend(check_stale_sources(conn, week_end))
    if not skip_url_check:
        findings.extend(check_broken_urls(conn))
    return findings


def format_findings(findings: Iterable[Finding]) -> list[str]:
    """Render findings as lines prefixed with severity tags."""
    out = []
    for f in findings:
        tag = {"info": "[ok]", "warn": "[warn]", "block": "[BLOCK]"}.get(f.severity, "[?]")
        out.append(f"{tag} {f.gate}: {f.message}")
    return out
