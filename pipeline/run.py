"""Weekly pipeline runner.

Phase 2: SEC EDGAR Form D ingest, then news RSS ingest with entity resolution
to attach articles to existing companies, then a technology taxonomy
classifier pass over every company's accumulated text.

Usage:
  python -m pipeline.run --since 2026-04-15                # explicit start
  python -m pipeline.run --days 7                          # last 7 days
  python -m pipeline.run --days 2 --max-records 10         # quick smoke test
  python -m pipeline.run --days 7 --skip-news --skip-tags  # Form D only
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
from typing import Iterable

from collectors import news_rss, sec_edgar, seed as seed_collector
from pipeline import (
    classifier,
    db,
    enrich,
    entity_resolver,
    focus as focus_module,
    qa,
    review,
    snapshot as snapshot_module,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ingest_form_d(records: Iterable[sec_edgar.FormDRecord]) -> tuple[int, int]:
    """Write Form D records to the store. Returns (companies_touched, filings_written)."""
    now = _now_iso()
    companies_touched = 0
    filings_written = 0
    with db.connect() as conn:
        for rec in records:
            if not rec.company_name:
                continue
            # Form D filings are evidence of a funding event; the filing date
            # is our best proxy for "first funded" in Phase 1.
            funded_at = rec.filing_date
            focus = focus_module.infer_focus(rec.company_name, rec.industry_group)
            company_id = db.upsert_company(
                conn,
                name=rec.company_name,
                cik=rec.cik,
                state=rec.state,
                year_of_inc=rec.year_of_inc,
                entity_type=rec.entity_type,
                industry_group=rec.industry_group,
                focus=focus,
                observed_at=now,
                funded_at=funded_at,
            )
            db.upsert_filing(
                conn,
                accession=rec.accession,
                company_id=company_id,
                source=rec.source,
                filing_date=rec.filing_date,
                date_of_first_sale=rec.date_of_first_sale,
                total_offering_amount=rec.total_offering_amount,
                filing_url=rec.filing_url,
                observed_at=now,
            )
            companies_touched += 1
            filings_written += 1
    return companies_touched, filings_written


def ingest_seed(records: list[seed_collector.SeedRecord]) -> int:
    """Upsert the curated seed list of known healthtech companies.

    Returns count of companies touched. Uses a historical observed_at so
    seeded rows never count as "surfaced this week".
    """
    touched = 0
    with db.connect() as conn:
        for rec in records:
            if not rec.name:
                continue
            db.upsert_company(
                conn,
                name=rec.name,
                cik=None,
                state=rec.state,
                year_of_inc=rec.year_of_inc,
                entity_type=rec.entity_type,
                industry_group=rec.industry_group,
                focus=rec.focus,
                observed_at=seed_collector.SEED_OBSERVED_AT,
                funded_at=None,
            )
            touched += 1
    return touched


def ingest_news(articles: list[news_rss.Article]) -> tuple[int, int, int]:
    """Attach articles to known companies via entity resolution.

    Returns (articles_scanned, articles_matched, attachments_written).
    An article that mentions N companies counts as N attachments.
    """
    now = _now_iso()
    scanned = 0
    matched = 0
    attachments = 0
    with db.connect() as conn:
        matcher = entity_resolver.build_company_matcher(db.all_company_names(conn))
        if not matcher:
            print("[news] no matchable companies in store yet, skipping attach")
            return (len(articles), 0, 0)
        for art in articles:
            scanned += 1
            blob = " . ".join(x for x in [art.title, art.summary] if x)
            hits = entity_resolver.find_mentions(blob, matcher)
            if not hits:
                continue
            matched += 1
            for company_id in hits:
                db.upsert_article(
                    conn,
                    company_id=company_id,
                    source=art.source,
                    title=art.title,
                    url=art.url,
                    summary=art.summary,
                    published_at=art.published_at,
                    observed_at=now,
                )
                attachments += 1
    return scanned, matched, attachments


def tag_all_companies() -> tuple[int, int]:
    """Run technology taxonomy classifier over every company's accumulated text.

    Returns (companies_scanned, companies_with_tags).
    Replaces all existing tags for each company so tag state is deterministic.
    """
    now = _now_iso()
    scanned = 0
    tagged = 0
    with db.connect() as conn:
        rows = list(db.all_companies_with_text(conn))
        for row in rows:
            scanned += 1
            texts = [
                row["name_display"] or "",
                row["industry_group"] or "",
                row["focus"] or "",
                row["article_titles"] or "",
                row["article_summaries"] or "",
            ]
            tags = classifier.classify(texts)
            db.replace_tech_tags(
                conn,
                company_id=row["id"],
                tags=[(t.category, t.confidence) for t in tags],
                tagged_at=now,
            )
            if tags:
                tagged += 1
    return scanned, tagged


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the weekly ingestion pipeline.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--since", type=lambda s: date.fromisoformat(s),
                       help="Start date (YYYY-MM-DD). Defaults to 7 days ago.")
    group.add_argument("--days", type=int, default=7,
                       help="Window size in days (default 7).")
    parser.add_argument("--until", type=lambda s: date.fromisoformat(s),
                        default=None, help="End date (YYYY-MM-DD). Defaults to today.")
    parser.add_argument("--max-records", type=int, default=None,
                        help="Cap number of Form D records fetched (for quick testing).")
    parser.add_argument("--all-industries", action="store_true",
                        help="Disable healthcare industry filter (debug only).")
    parser.add_argument("--skip-seed", action="store_true",
                        help="Skip the curated-seed upsert.")
    parser.add_argument("--skip-form-d", action="store_true",
                        help="Skip the SEC EDGAR Form D ingest step.")
    parser.add_argument("--skip-news", action="store_true",
                        help="Skip the news RSS + entity resolution step.")
    parser.add_argument("--skip-tags", action="store_true",
                        help="Skip the technology taxonomy classifier pass.")
    parser.add_argument("--skip-enrich", action="store_true",
                        help="Skip the description-enrichment step (news + web scrape).")
    parser.add_argument("--no-web-scrape", action="store_true",
                        help="Run enrichment but skip the DuckDuckGo + meta-description fallback.")
    parser.add_argument("--enrich-limit", type=int, default=15,
                        help="Number of top recent companies to enrich (default 15).")
    parser.add_argument("--enrich-window-days", type=int, default=30,
                        help="Lookback window in days for the enrich step (default 30).")
    parser.add_argument("--skip-snapshot", action="store_true",
                        help="Skip the weekly snapshot + report writer.")
    parser.add_argument("--skip-qa", action="store_true",
                        help="Skip the QA gates.")
    parser.add_argument("--skip-review", action="store_true",
                        help="Skip regenerating review/pending.md.")
    parser.add_argument("--skip-url-check", action="store_true",
                        help="Skip the broken-URL sample check (network).")
    args = parser.parse_args()

    end = args.until or date.today()
    if args.since:
        start = args.since
    else:
        start = end - timedelta(days=args.days)

    print(f"[pipeline] initializing database at {db.DB_PATH}")
    db.init_db()

    if not args.skip_seed:
        seeds = seed_collector.collect()
        touched = ingest_seed(seeds)
        print(f"[pipeline] seeded {touched} known healthtech companies")
    else:
        print("[pipeline] skipping seed step")

    if not args.skip_form_d:
        print(f"[pipeline] fetching Form D filings from {start} to {end}")
        records = sec_edgar.collect(
            start=start,
            end=end,
            only_healthcare=not args.all_industries,
            max_records=args.max_records,
        )
        print(f"[pipeline] got {len(records)} Form D records after filter")
        companies_touched, filings_written = ingest_form_d(records)
        print(f"[pipeline] upserted {companies_touched} companies, wrote {filings_written} filings")
    else:
        print("[pipeline] skipping Form D step")

    if not args.skip_news:
        print(f"[pipeline] fetching healthtech news from {start} to {end}")
        articles = news_rss.collect(start, end)
        print(f"[pipeline] got {len(articles)} articles across feeds")
        scanned, matched, attachments = ingest_news(articles)
        print(f"[pipeline] scanned {scanned} articles, {matched} matched a known company "
              f"({attachments} attachments)")
    else:
        print("[pipeline] skipping news step")

    if not args.skip_tags:
        print("[pipeline] running technology taxonomy classifier")
        scanned, tagged = tag_all_companies()
        print(f"[pipeline] tagged {tagged} of {scanned} companies with >=1 technology category")
    else:
        print("[pipeline] skipping classifier step")

    if not args.skip_enrich:
        enrich_since = end - timedelta(days=args.enrich_window_days)
        print(f"[pipeline] enriching top {args.enrich_limit} companies funded since {enrich_since}")
        with db.connect() as conn:
            scanned, from_news, from_web, skipped = enrich.enrich_top_recent(
                conn,
                since=enrich_since,
                limit=args.enrich_limit,
                now_iso=_now_iso(),
                allow_web=not args.no_web_scrape,
            )
        print(f"[pipeline] enriched: scanned={scanned} news={from_news} web={from_web} "
              f"skipped_cached={skipped}")
    else:
        print("[pipeline] skipping enrich step")

    findings: list[qa.Finding] = []
    if not args.skip_qa:
        with db.connect() as conn:
            findings = qa.run_all(conn, week_end=end, skip_url_check=args.skip_url_check)
        print("[pipeline] QA findings:")
        for line in qa.format_findings(findings):
            print(f"  {line}")
    else:
        print("[pipeline] skipping QA step")

    if not args.skip_snapshot:
        print(f"[pipeline] computing weekly snapshot for {start}..{end}")
        with db.connect() as conn:
            snap = snapshot_module.compute(conn, week_start=start, week_end=end)
            if findings:
                snap.notes.extend(qa.format_findings(findings))
            snapshot_module.persist(conn, snap)
            report_path = snapshot_module.write_markdown(snap)
        print(f"[pipeline] snapshot: funded={snap.new_funded_count} "
              f"surfaced={snap.new_surfaced_count} founded={snap.new_founded_count}")
        print(f"[pipeline] wrote report to {report_path}")
    else:
        print("[pipeline] skipping snapshot step")

    if not args.skip_review:
        with db.connect() as conn:
            review_path = review.generate(conn)
        print(f"[pipeline] wrote review queue to {review_path}")
    else:
        print("[pipeline] skipping review-queue step")


if __name__ == "__main__":
    main()
