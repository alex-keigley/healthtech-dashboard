"""SEC EDGAR Form D collector.

Form D is the notice-of-sale filing that private US companies must submit
within 15 days of raising capital under Regulation D. For our purposes it's
the best free signal that a healthcare-technology startup has just raised.

Pipeline:
  1. For each date in the window, fetch the daily master index
     (`master.YYYYMMDD.idx` — pipe-delimited, all filings that day).
  2. Keep rows where Form Type == "D".
  3. For each Form D row, fetch the filing's primary_doc.xml.
  4. Parse out company, state, industry group, and offering amount.
  5. Filter to healthcare industry groups.

The daily master index is used (rather than the full-text search) because
Form D is a short notice filing that isn't reliably indexed by the
full-text search.

SEC requires a descriptive User-Agent identifying the requester (contact
info included) on every request. Configure via the SEC_USER_AGENT env var;
falls back to a generic default that still identifies the project.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterator, Optional
from xml.etree import ElementTree as ET

import requests

DEFAULT_USER_AGENT = "healthtech-dashboard/1.0 (contact: set SEC_USER_AGENT env var)"
DAILY_INDEX_BASE = "https://www.sec.gov/Archives/edgar/daily-index"
ARCHIVE_BASE = "https://www.sec.gov/Archives/edgar/data"

HEALTHCARE_INDUSTRY_GROUPS = {
    "Biotechnology",
    "Health Insurance",
    "Hospitals & Physicians",
    "Pharmaceuticals",
    "Other Health Care",
}

REQUEST_DELAY_SECONDS = 0.2


def _user_agent() -> str:
    return os.environ.get("SEC_USER_AGENT") or DEFAULT_USER_AGENT


@dataclass
class FormDRecord:
    accession: str
    cik: str
    company_name: str
    filing_date: Optional[str]
    filing_url: str
    state: Optional[str] = None
    industry_group: Optional[str] = None
    year_of_inc: Optional[str] = None
    entity_type: Optional[str] = None
    total_offering_amount: Optional[float] = None
    date_of_first_sale: Optional[str] = None
    source: str = "sec_edgar_form_d"


@dataclass
class IndexHit:
    cik: str
    company_name: str
    form_type: str
    date_filed: str  # YYYYMMDD
    accession: str
    file_url: str


def _quarter(d: date) -> int:
    return (d.month - 1) // 3 + 1


def _daterange(start: date, end: date) -> Iterator[date]:
    cur = start
    while cur <= end:
        yield cur
        cur = cur + timedelta(days=1)


def _parse_accession(file_name: str) -> Optional[str]:
    """Extract an accession like '0001104659-26-045882' from a file name column."""
    tail = file_name.rsplit("/", 1)[-1]
    for suffix in (".txt", ".htm", ".html"):
        if tail.endswith(suffix):
            tail = tail[: -len(suffix)]
            break
    # Valid accessions look like NNNNNNNNNN-NN-NNNNNN
    parts = tail.split("-")
    if len(parts) == 3 and all(p.isdigit() for p in parts):
        return tail
    return None


class SecEdgarClient:
    def __init__(self, user_agent: Optional[str] = None):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent or _user_agent()})

    def _get(self, url: str, **kwargs) -> Optional[requests.Response]:
        try:
            r = self.session.get(url, timeout=30, **kwargs)
        except requests.RequestException:
            return None
        time.sleep(REQUEST_DELAY_SECONDS)
        if r.status_code == 404:
            return None
        try:
            r.raise_for_status()
        except requests.HTTPError:
            return None
        return r

    def fetch_daily_master_index(self, d: date) -> Optional[str]:
        """Fetch the daily master index for a given date. Returns None for weekends/holidays."""
        url = (
            f"{DAILY_INDEX_BASE}/{d.year}/QTR{_quarter(d)}/master.{d.strftime('%Y%m%d')}.idx"
        )
        r = self._get(url, headers={"Accept": "text/plain"})
        return r.text if r else None

    def iter_form_d_hits(self, start: date, end: date) -> Iterator[IndexHit]:
        """Yield Form D hits from the daily master indexes in [start, end]."""
        for d in _daterange(start, end):
            text = self.fetch_daily_master_index(d)
            if not text:
                continue
            in_table = False
            for line in text.splitlines():
                if not in_table:
                    # Rows start after the header separator line (a long run of dashes)
                    if line.startswith("---"):
                        in_table = True
                    continue
                parts = line.split("|")
                if len(parts) != 5:
                    continue
                cik, company, form_type, date_filed, file_name = parts
                if form_type.strip() != "D":
                    continue
                accession = _parse_accession(file_name.strip())
                if not accession:
                    continue
                yield IndexHit(
                    cik=cik.strip(),
                    company_name=company.strip(),
                    form_type="D",
                    date_filed=date_filed.strip(),
                    accession=accession,
                    file_url=f"https://www.sec.gov/{file_name.strip()}",
                )

    def fetch_form_d_xml(self, cik: str, accession: str) -> Optional[str]:
        cik_int = int(cik)
        accession_nodashes = accession.replace("-", "")
        url = f"{ARCHIVE_BASE}/{cik_int}/{accession_nodashes}/primary_doc.xml"
        r = self._get(url, headers={"Accept": "application/xml"})
        return r.text if r else None


def _strip_namespaces(root: ET.Element) -> None:
    for el in root.iter():
        if "}" in el.tag:
            el.tag = el.tag.split("}", 1)[1]


def _text(parent: ET.Element, path: str) -> Optional[str]:
    el = parent.find(path)
    if el is None or el.text is None:
        return None
    return el.text.strip() or None


def parse_form_d(xml_text: str) -> dict:
    """Parse a Form D primary_doc.xml into a flat dict of fields we care about."""
    result: dict = {}
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return result
    _strip_namespaces(root)

    primary = root.find(".//primaryIssuer")
    if primary is not None:
        result["company_name"] = _text(primary, "entityName")
        addr = primary.find("issuerAddress")
        if addr is not None:
            result["state"] = _text(addr, "stateOrCountry")
        year = _text(primary, "yearOfInc/yearOfIncValue") or _text(primary, "yearOfInc/value")
        result["year_of_inc"] = year
        result["entity_type"] = _text(primary, "entityType")

    offering = root.find(".//offeringData")
    if offering is not None:
        result["industry_group"] = _text(offering, "industryGroup/industryGroupType")
        total_text = _text(offering, "offeringSalesAmounts/totalOfferingAmount")
        if total_text:
            try:
                result["total_offering_amount"] = float(total_text)
            except ValueError:
                pass
        result["date_of_first_sale"] = _text(offering, "dateOfFirstSale/value")

    return result


def collect(
    start: date,
    end: date,
    only_healthcare: bool = True,
    max_records: Optional[int] = None,
) -> list[FormDRecord]:
    """Fetch and parse Form D filings in the date window. Returns filtered records.

    Degrades gracefully: network errors on individual requests are absorbed
    by SecEdgarClient._get (returns None -> skip), so a partial/total outage
    yields an empty or short list rather than an exception.
    """
    client = SecEdgarClient()
    records: list[FormDRecord] = []
    for hit in client.iter_form_d_hits(start, end):
        xml = client.fetch_form_d_xml(hit.cik, hit.accession)
        if not xml:
            continue
        parsed = parse_form_d(xml)
        industry = parsed.get("industry_group")
        if only_healthcare and industry not in HEALTHCARE_INDUSTRY_GROUPS:
            continue
        filing_url = (
            f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={hit.cik}&type=D"
        )
        # Prefer the name parsed from the XML (punctuation-accurate) over the index line.
        company_name = parsed.get("company_name") or hit.company_name
        filing_date_iso = _idx_date_to_iso(hit.date_filed)
        records.append(
            FormDRecord(
                accession=hit.accession,
                cik=hit.cik,
                company_name=company_name,
                state=parsed.get("state"),
                industry_group=industry,
                year_of_inc=parsed.get("year_of_inc"),
                entity_type=parsed.get("entity_type"),
                total_offering_amount=parsed.get("total_offering_amount"),
                date_of_first_sale=parsed.get("date_of_first_sale"),
                filing_date=filing_date_iso,
                filing_url=filing_url,
            )
        )
        if max_records and len(records) >= max_records:
            break
    return records


def _idx_date_to_iso(yyyymmdd: str) -> Optional[str]:
    if len(yyyymmdd) != 8 or not yyyymmdd.isdigit():
        return None
    return f"{yyyymmdd[:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:8]}"


if __name__ == "__main__":
    from datetime import timedelta

    end = date.today()
    start = end - timedelta(days=7)
    recs = collect(start, end)
    print(f"Fetched {len(recs)} healthcare Form D filings from {start} to {end}")
    for r in recs[:5]:
        print(r)
