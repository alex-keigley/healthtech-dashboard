# Healthtech Startup Dashboard

A weekly-updated dashboard tracking new US healthcare technology startups
and maintaining a curated, browsable repository tagged with technology
categories.

**Audience:** healthcare IT professionals, executives, and students. Every
data point is traceable to a public source; see [METHODOLOGY.md](METHODOLOGY.md)
for the full doctrine.

---

## What it does

Every week, the pipeline fetches three streams of public data, resolves
entities against the existing repository, and classifies every company
against an 18-category technology taxonomy:

- **SEC EDGAR Form D filings** — private-company capital raises in five
  healthcare industry groups (primary signal for "newly funded").
- **Healthtech trade news** (MobiHealthNews, Fierce Healthcare, Healthcare
  IT News, Rock Health) — articles attached to companies already in the
  repository to enrich their text profile.
- **Curated seed list** of well-known US digital-health companies — so
  the news matcher has something to match against even while the Form D
  cohort is small.
- **SBIR/STTR awards** — *(collector ready; API currently offline)*.

Three independent "new" signals are tracked each week (*newly funded*,
*newly surfaced*, *newly founded*), not collapsed into one — see the
methodology for why.

The output lands in a local SQLite store (`data/startups.db`), a weekly
markdown report (`reports/<week_start>.md`), a human-review queue
(`review/pending.md`), and a Streamlit dashboard.

## Dashboard

Seven pages:

| Page | What it shows |
|---|---|
| Overview | Top healthtech companies in the past 30 days, with descriptions |
| Startup Explorer | Every tracked company with technology tags + per-company detail |
| Trends | Weekly filing volume, state distribution, raise histogram |
| Technology Lens | Per-category deep dive |
| Weekly report | Auto-generated markdown summary |
| Review queue | Untagged, low-confidence, fuzzy-match items awaiting review |
| Methodology | Public methodology document |

## Local setup

Requires Python 3.10+.

```bash
pip install -r requirements.txt

# Create the database schema
python -m pipeline.db

# Run the full pipeline for the last 7 days
python -m pipeline.run --days 7

# Launch the dashboard
streamlit run app.py
```

The SQLite DB, weekly report, and review queue are all committed to the
repo so history is auditable and Streamlit Cloud can redeploy on push.

## Pipeline commands

```bash
# Default: last 7 days, all stages
# (seed -> Form D -> news -> tags -> QA -> snapshot -> review)
python -m pipeline.run --days 7

# Explicit window
python -m pipeline.run --since 2026-04-01 --until 2026-04-07

# Skip individual stages
python -m pipeline.run --days 7 --skip-form-d --skip-news
python -m pipeline.run --days 7 --skip-tags
python -m pipeline.run --days 7 --skip-qa --skip-snapshot --skip-review

# Skip network checks (offline)
python -m pipeline.run --days 7 --skip-url-check
```

## Contributing

The repository is community-maintained. Volunteers work the review queue
by submitting pull requests:

1. Open [`review/pending.md`](review/pending.md).
2. Pick an item you can resolve from public sources (company website,
   press coverage, SEC filing detail).
3. Open a PR that:
   - Edits the relevant row in the data files (for tag corrections), OR
   - Proposes a merge between two records (for fuzzy-match candidates),
     preserving the earlier `first_funded_at` / `first_surfaced_at`, OR
   - Leaves an untagged company untagged with a comment explaining why
     (e.g. "holding LLC, not a tech startup").
4. Reference the source that supports your edit in the PR description.

For non-correction feedback (taxonomy gaps, new sources, feature ideas)
open a GitHub issue.

## Automation

The pipeline runs every Sunday at 06:00 UTC via GitHub Actions (see
[`.github/workflows/weekly.yml`](.github/workflows/weekly.yml)). Each
run commits the refreshed `data/startups.db`, `reports/<week_start>.md`,
and `review/pending.md` to the main branch, triggering a Streamlit Cloud
redeploy.

## Forking / adapting

Nothing in the pipeline is region-specific — the Form D feed, news
feeds, and seed list all default to a US-national scope. To narrow:

1. Fork this repository.
2. Adjust the hero caption in `app.py` and the methodology doc.
3. Optionally narrow the Form D filter by state
   (edit `collectors/sec_edgar.py`).
4. Add any region-specific seed companies to `collectors/seed.py`.

The data is public and the code is open.

## Project layout

```
collectors/         — one module per data source
  sec_edgar.py      — SEC Form D daily master index
  sbir.py           — SBIR/STTR awards (stub; API offline)
  news_rss.py       — healthtech trade news RSS
  seed.py           — curated list of known healthtech companies
pipeline/           — normalize, tag, QA, write
  db.py             — SQLite schema + canonical-name helpers
  entity_resolver.py — fuzzy name match + regex matcher
  focus.py          — heuristic focus labels from company names
  classifier.py     — technology taxonomy rule-based tagger
  qa.py             — automated gates (spike, orphan, stale, URL)
  snapshot.py       — weekly counts + markdown report writer
  review.py         — review/pending.md generator
  run.py            — pipeline runner (CLI)
data/               — startups.db (committed)
reports/            — weekly markdown reports (committed)
review/             — pending.md + rejected.jsonl (committed)
app.py              — Streamlit dashboard
.github/workflows/  — weekly cron
```

## Licensing

All data presented here comes from public US government filings and
publicly-distributed RSS feeds. The dashboard code and derived tagging
are open-source; formal license file coming in Phase 4 follow-up.
# healthtech-dashboard
