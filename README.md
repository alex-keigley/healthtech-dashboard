# Healthtech Startup Dashboard 1.0

A self-hosted, human-reviewed repository of newly funded and newly surfaced
US healthcare-technology startups, built from public SEC filings and trade
press. Complete rewrite of the Streamlit POC for production self-hosting.

**Audience:** healthcare physicians, administrators, and executives — many of
them HIMSS members — who want to see what new healthtech companies exist.
Every data point is traceable to a public source and passes through human
review before publication; see [METHODOLOGY.md](METHODOLOGY.md).

---

## What's here

- **Public one-pager** — the entire public experience lives on a single page:
  hero stats (three "new" signals), this week's companies, a searchable and
  filterable explorer, and trends. Tapping any company opens a detail drawer
  (description, tags, SEC filings, news) without leaving the page. The only
  off-page link is the [methodology](METHODOLOGY.md), published separately so
  it can be scrutinized at the scientific level.
- **Data pipeline** (Python) — weekly ingest of SEC EDGAR Form D filings,
  healthtech trade RSS, a curated seed list, and SBIR/STTR awards; entity
  resolution, an 18-category rule-based classifier, QA gates. New records
  land as *pending review* — nothing is published automatically.
- **Reviewer tool** — authenticated workbench to validate, edit, tag, merge,
  or invalidate records, with every change written to an append-only audit
  log (`revisions`).
- **Admin panel** — user/role management, site presentation settings,
  pipeline run history.
- **Auth** — invite-only email accounts; sign in with a password or a
  one-time emailed code. Roles: **Viewer** (same view as the public),
  **Reviewer** (works the review queue), **Admin** (full control).

## Architecture

```
caddy (TLS) ──► web (Next.js 15)  ──┐
                                    ├──► data/app.db  (SQLite, WAL)
pipeline-cron (Python, Sunday 06:00 UTC) ┘
```

One SQLite file is the whole data layer — appropriate for this write volume
(one weekly batch + occasional reviewer edits). Schema source of truth:
[`db/migrations/0001_init.sql`](db/migrations/0001_init.sql); both apps apply
migrations idempotently.

## Quick start (local development — Windows/macOS/Linux)

Requires Node 20+ and Python 3.10+.

```bash
cp .env.example .env          # edit: ADMIN_EMAIL/PASSWORD, SEC_USER_AGENT

# Web app
cd web
npm install
npm run db:migrate            # creates ../data/app.db
npm run seed:admin            # first admin from ADMIN_EMAIL/ADMIN_PASSWORD
npm run dev                   # http://localhost:3000

# Pipeline (separate terminal; fills the review queue)
cd pipeline
pip install -r requirements.txt
python -m pipeline.run --days 7
```

With `SMTP_HOST` unset, one-time login codes print to the web server console
instead of sending email — no mail setup needed in dev.

## Production install (Linux box / homelab / cloud VM)

Requires Docker + Docker Compose v2.

```bash
git clone https://github.com/alex-keigley/healthtech-dashboard.git
cd healthtech-dashboard
cp .env.example .env    # set ADMIN_EMAIL/PASSWORD, SEC_USER_AGENT,
                        # SMTP_* (for login codes), SITE_URL, and SITE_DOMAIN
docker compose up -d --build
```

That starts three containers: `web` (applies migrations and seeds the admin
on boot), `pipeline-cron` (weekly ingest, Sunday 06:00 UTC), and `caddy`
(reverse proxy; set `SITE_DOMAIN` to a real hostname pointed at the box and
Caddy provisions HTTPS automatically). The database lives in `./data/` on
the host — **back it up by copying that directory** (e.g. nightly cron with
`sqlite3 .backup` or a plain file copy while the site is quiet).

Manual pipeline run:

```bash
docker compose run --rm pipeline-cron python -m pipeline.run --days 7
```

## Cloud hosting sizing

The stack is light: Next.js idles around 150–300 MB, the pipeline is a
short-lived weekly batch job that is network-bound (SEC/RSS fetches with
politeness delays), and SQLite adds no server overhead. A burstable
2 GB / 2 vCPU instance is comfortable for both the site and the weekly
acquisition run; 1 GB works if you add swap for `docker compose build`
(or build images elsewhere and pull them).

| | AWS (EC2) | GCP (Compute Engine) | Azure (VM) | Approx. cost* |
|---|---|---|---|---|
| **Minimum** | t3.micro — 2 vCPU, 1 GB | e2-micro — 2 vCPU, 1 GB | B1s — 1 vCPU, 1 GB | ~$7–10/mo |
| **Recommended** | t3.small — 2 vCPU, 2 GB | e2-small — 2 vCPU, 2 GB | B2ats v2 — 2 vCPU, 1–2 GB (or B1ms) | ~$15–20/mo |
| **Headroom** (growth, many reviewers) | t3.medium — 2 vCPU, 4 GB | e2-medium — 2 vCPU, 4 GB | B2s — 2 vCPU, 4 GB | ~$30–40/mo |

*On-demand US-region prices, approximate as of mid-2026 — check each
provider's calculator. All tiers: **20 GB** of standard SSD storage is ample
(the database is measured in megabytes). No managed database, cache, or
object storage is required. Container-service equivalents (ECS Fargate,
Cloud Run, Container Apps) work but complicate SQLite's need for a
persistent local disk — a plain VM is the intended target.

## Roles & access

| Role | Access |
|---|---|
| Public (no account) | One-pager + methodology; published records only |
| Viewer | Same as public (a provisioning state before promotion) |
| Reviewer | + `/review`: queue, record workbench, merge tool, QA runs |
| Admin | + `/admin`: users/roles, presentation settings, pipeline status |

Accounts are invite-only — an admin creates them in `/admin/users`. The
publish policy defaults to **fail-closed** (nothing public until a reviewer
validates); admins can switch to *auto-publish with "unreviewed" badge* in
`/admin/settings` if the queue backs up.

## Pipeline commands

```bash
cd pipeline
python -m pipeline.run --days 7                    # default weekly window
python -m pipeline.run --since 2026-06-01 --until 2026-06-07
python -m pipeline.run --days 7 --skip-news --skip-tags
python -m pipeline.run --days 3 --max-records 25 --skip-url-check   # smoke test
```

See [pipeline/README.md](pipeline/README.md) for all flags and env vars.
`SEC_USER_AGENT` must identify you (SEC requirement).

## Project layout

```
web/                Next.js 15 app — public site, auth, reviewer + admin tools
pipeline/           Python — collectors, classifier, QA, review-queue writer
db/migrations/      SQL schema (single source of truth, applied by both apps)
data/               app.db (gitignored; created on first run)
deploy/             web.Dockerfile, Caddyfile, crontab, entrypoint
docker-compose.yml  web + pipeline-cron + caddy
METHODOLOGY.md      public methodology (rendered at /methodology)
PLAN.md             1.0 rebuild plan (design record)
```

## License

[MIT](LICENSE). All data comes from public US government filings and
publicly distributed RSS feeds.
