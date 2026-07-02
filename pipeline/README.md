# Healthtech Dashboard — pipeline

Python data pipeline: SEC EDGAR Form D + curated seed list + healthtech news
RSS, entity resolution, a rule-based technology-taxonomy classifier,
description enrichment, QA gates, weekly snapshot, and review-queue
population. Ported from the original Streamlit POC; writes into the shared
SQLite database defined by `db/migrations/0001_init.sql` at the repo root.

## Layout

This package is nested one level deep on purpose:

```
pipeline/                  <- repo-relative package root (this dir)
  collectors/               sec_edgar, news_rss, sbir, seed, web_about
  pipeline/                  db, entity_resolver, classifier, focus, qa,
                              enrich, snapshot, review, run
  requirements.txt
  Dockerfile
```

**Run it from inside `pipeline/`** so `python -m pipeline.run` resolves the
`pipeline` package correctly:

```bash
cd pipeline
python -m pipeline.run --days 7
```

Do NOT run `python -m pipeline.run` from the repo root — the package dir is
`pipeline/pipeline`, and the module path only resolves with `pipeline/` (this
directory) as cwd.

## Setup

```bash
cd pipeline
python3 -m venv .venv
source .venv/bin/activate      # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
```

## Environment variables

| Var | Default | Purpose |
|---|---|---|
| `DATABASE_PATH` | `../data/app.db` (resolved from repo root, robust to cwd) | Shared SQLite file. WAL mode, `busy_timeout=5000`, `foreign_keys=ON`. |
| `SEC_USER_AGENT` | generic fallback (set this!) | SEC EDGAR requires a descriptive User-Agent identifying the requester, e.g. `"healthtech-dashboard/1.0 (contact: you@example.com)"`. |

If `DATABASE_PATH` is unset, `pipeline/pipeline/db.py` walks up from its own
file location to the repo root and uses `data/app.db` there — this works
whether you run from `pipeline/` (the documented way) or invoke the module
some other way. If `DATABASE_PATH` is a relative path, it resolves against
the current working directory, matching the web app's `migrate.mjs`
convention.

The pipeline applies `db/migrations/*.sql` itself on every `init_db()` call
(same `_migrations(name, applied_at)` bookkeeping as `web/scripts/migrate.mjs`),
so it can be run standalone before the web app has ever started.

## Commands

```bash
# Full weekly run (default 7-day window)
python -m pipeline.run

# Explicit window
python -m pipeline.run --since 2026-06-01 --until 2026-06-30

# Quick smoke test against live sources
python -m pipeline.run --days 3 --max-records 25 --skip-url-check --no-web-scrape

# Skip stages
python -m pipeline.run --skip-seed --skip-form-d --skip-news --skip-tags \
  --skip-enrich --skip-snapshot --skip-qa --skip-review

# Other flags
#   --all-industries        disable healthcare industry filter (debug only)
#   --enrich-limit N         companies to enrich per run (default 15)
#   --enrich-window-days N   lookback window for enrichment (default 30)
```

## What changed vs. the POC

- New company rows are inserted with `status='pending_review'` (the schema
  default) — the pipeline never sets `'published'`.
- Fields on existing companies are never overwritten if a human has an
  `edit` revision for that field (checked against the `revisions` table).
- `tech_tags.origin='machine'` rows are the only ones the classifier
  touches; `origin='human'` rows are never modified or deleted.
- The review queue is rows in `review_items` (`new_record`, `untagged`,
  `low_confidence`, `fuzzy_match`), not `review/pending.md`.
- Every run is recorded in `pipeline_runs` (status, per-source stats, QA
  findings as JSON) instead of only printing to stdout.
- No markdown reports are written and nothing is committed to git — the web
  app reads directly from the database.

## Docker

```bash
docker build -t healthtech-pipeline -f Dockerfile ..
docker run --rm -e SEC_USER_AGENT="you@example.com" \
  -v $(pwd)/../data:/app/data healthtech-pipeline
```

The default command runs `python -m pipeline.run --days 7`, intended to be
invoked on a weekly schedule (see the repo-root `deploy/` compose + cron
setup).
