"""SBIR/STTR collector.

As of this writing, the SBIR.gov Public API returns 429 'not available at
this time' globally. This module is a forward-compatible stub: when the
API recovers, the existing `collect()` call site will pick up results
automatically. Until then, it returns an empty list and logs a skip.

Endpoint reference (for when it's back):
  https://api.www.sbir.gov/public/api/awards
Params: agency=HHS, year, start, rows (max ~100).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date
from typing import Optional

import requests

USER_AGENT = "healthtech-dashboard/1.0 (+sbir collector)"
API_URL = "https://api.www.sbir.gov/public/api/awards"
REQUEST_DELAY_SECONDS = 1.0  # Be conservative with the public API


@dataclass
class SbirRecord:
    firm: str
    state: Optional[str]
    agency: str
    phase: Optional[str]
    program: Optional[str]
    award_year: Optional[int]
    award_amount: Optional[float]
    award_date: Optional[str]
    title: Optional[str]
    abstract: Optional[str]
    source: str = "sbir_awards"


def collect(start: date, end: date, agency: str = "HHS") -> list[SbirRecord]:
    """Fetch HHS SBIR/STTR awards in the date window. Returns [] if API is down."""
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    results: list[SbirRecord] = []
    page_size = 100
    start_idx = 0
    years = sorted({start.year, end.year})

    for year in years:
        while True:
            params = {
                "agency": agency,
                "year": year,
                "rows": page_size,
                "start": start_idx,
            }
            try:
                r = requests.get(API_URL, params=params, headers=headers, timeout=30)
            except requests.RequestException as e:
                print(f"[sbir] network error, skipping: {e}")
                return results
            if r.status_code == 429:
                # Service-wide outage seen in Apr 2026; skip gracefully
                print(f"[sbir] API 429 ({r.json().get('Message', 'throttled') if 'json' in r.headers.get('Content-Type','') else 'throttled'}) — skipping SBIR this run")
                return results
            if not r.ok:
                print(f"[sbir] unexpected {r.status_code}, skipping: {r.text[:120]}")
                return results
            try:
                batch = r.json()
            except ValueError:
                print(f"[sbir] non-JSON response, skipping")
                return results
            if not isinstance(batch, list) or not batch:
                break
            for item in batch:
                award_date = item.get("proposal_award_date") or item.get("award_date")
                if award_date and (start.isoformat() <= award_date[:10] <= end.isoformat()):
                    results.append(SbirRecord(
                        firm=item.get("firm") or "",
                        state=item.get("state"),
                        agency=item.get("agency") or agency,
                        phase=item.get("phase"),
                        program=item.get("program"),
                        award_year=item.get("award_year"),
                        award_amount=_to_float(item.get("award_amount")),
                        award_date=award_date[:10] if award_date else None,
                        title=item.get("award_title"),
                        abstract=item.get("abstract"),
                    ))
            if len(batch) < page_size:
                break
            start_idx += page_size
            time.sleep(REQUEST_DELAY_SECONDS)
        start_idx = 0
    return results


def _to_float(v) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None
