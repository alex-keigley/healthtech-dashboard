# Healthtech Dashboard 1.0 — Rebuild Plan

Rewrite of the Streamlit POC (github.com/alex-keigley/healthtech-dashboard) into a self-hostable product.

**Decisions locked in:** Next.js web app + Python pipeline, SQLite, Docker Compose for deployment. Dev happens natively on Windows; homelab Linux box is the interim host; cloud VM is the eventual target.

---

## 1. Architecture

```
┌─────────────────────────────────────────────────────────┐
│ Docker Compose (prod)          │ Windows dev (native)   │
│                                │                        │
│  caddy ──► web (Next.js)       │  npm run dev           │
│            │                   │  python -m pipeline... │
│  scheduler ─► pipeline (Py)    │                        │
│            │                   │                        │
│        data/app.db  (SQLite, WAL mode, shared volume)   │
└─────────────────────────────────────────────────────────┘
```

- **web** — Next.js 15 (App Router, TypeScript). Serves the public one-pager, methodology page, reviewer tool, admin panel, and auth. Reads/writes SQLite via Drizzle ORM + better-sqlite3.
- **pipeline** — the POC's Python collectors/pipeline, ported mostly intact (collectors, entity resolver, classifier, QA gates are the POC's proven value — keep them). Writes new records as `pending_review` instead of auto-publishing. Run weekly by a lightweight cron container (supercronic), replacing GitHub Actions.
- **SQLite** — single file, WAL mode. Writers: pipeline (weekly batch) and web (reviewer edits). At this volume (~40 records/week) contention is a non-issue with WAL + busy_timeout. **Fresh start: no POC data is migrated.** The first pipeline run populates the review queue.
- **caddy** — TLS + reverse proxy in prod. Not used in dev.

Repo layout:

```
web/            Next.js app
pipeline/       Python (collectors/, pipeline/, migrate_poc.py)
data/           app.db (gitignored — no longer committed to repo)
deploy/         docker-compose.yml, Caddyfile, crontab, .env.example
METHODOLOGY.md  updated to describe the human-review workflow
README.md       install guide + cloud sizing
```

## 2. Database schema (delta from POC)

Keep: `companies`, `filings`, `articles`, `tech_tags`, `name_aliases`, `company_descriptions`, `weekly_snapshots`.

Add:

- `companies.status` — `pending_review | published | invalidated | archived`, plus `reviewed_by`, `reviewed_at`, `invalidation_reason`.
- `tech_tags.origin` — `machine | human`; human tags are never overwritten by the classifier.
- `revisions` — append-only audit log: who changed what field, old/new value, when. Grounds the methodology's provenance claims.
- `review_items` — replaces `review/pending.md`: typed queue rows (untagged / low-confidence / fuzzy-match / new-record) with state (`open | resolved | dismissed`), resolution note, assignee.
- `users` — email, password_hash (nullable), role (`viewer | reviewer | admin`), created/disabled.
- `otp_codes`, `sessions` — one-time email codes and session tokens.
- `site_settings` — admin-controlled presentation: featured categories, hero copy, cards-per-section, publish thresholds.

## 3. Auth & roles

Auth.js (NextAuth v5) with two credential flows against the same `users` table:

1. **Password** — bcrypt hash, standard form.
2. **One-time emailed password** — 6-digit code, 10-minute expiry, single use, rate-limited. Sent via SMTP (env-configured: any relay — SES, Resend, Mailgun, or homelab Postfix).

Roles:

| Role | Access |
|---|---|
| (public, no login) | Public one-pager + methodology — published data only |
| Viewer | Same as public (exists so accounts can be provisioned before promotion) |
| Reviewer | + Reviewer tool: validate, edit, invalidate records; work the queue |
| Admin | + User/role management; site presentation settings; full data control |

Middleware guards `/review/*` (reviewer+) and `/admin/*` (admin). Public routes need no session.

## 4. Reviewer tool (`/review`)

The POC's read-only review queue becomes an actionable workbench:

- **Queue dashboard** — counts by type/age; filter by state, source, week; claim items.
- **Record editor** — side-by-side: scraped values vs. editable fields (name, focus, description, tags with confidence, state, industry group), with source links (SEC filing, articles, scraped about-page) inline for verification. Actions: **Validate** (→ published), **Save edits** (logged to `revisions`), **Invalidate** (reason required; hidden from public, never deleted — matches methodology's "never silently deleted" promise).
- **Merge tool** — fuzzy-match pairs shown side-by-side; merge keeps earliest `first_funded_at`/`first_surfaced_at`, records alias, logs to `revisions`.
- **QA findings** — the pipeline's spike/orphan/stale/URL-check gate results, acknowledgeable per run.

Publishing policy (admin-configurable): default fail-closed — new pipeline records are public only after reviewer validation, consistent with the POC's trust-first doctrine. Optional "auto-publish with 'unreviewed' badge" mode if the queue backs up.

## 5. Public one-pager (`/`)

Single scrolling page; nothing requires navigation away. Designed for physicians, administrators, executives, HIMSS members — credible, scannable, mobile-friendly.

1. **Hero** — headline stats: companies tracked, new this week (funded / surfaced / founded — the POC's three signals, kept), last-updated stamp, "reviewed by humans" trust marker.
2. **This week's new companies** — card grid. **Tap a card → detail drawer/modal** (not a page): description, tech tags, focus, state, filings with SEC links, news articles, review status. Deep-linkable (`/?company=slug`) for sharing; closes back to the same scroll position.
3. **Explorer** — the full published repository inline: search, filter by the 18-category taxonomy / state / week; same tap-to-detail behavior.
4. **Trends** — weekly filing volume, category distribution, state map (Recharts).
5. **Footer** — link to Methodology (the one intentional off-page link), about, sign-in.

`/methodology` stays a separate page: current METHODOLOGY.md content updated to document the human-review layer (who reviews, what validation means, audit trail) so it withstands scientific scrutiny.

## 6. Admin panel (`/admin`)

- **Users** — invite by email, assign/change roles, disable accounts.
- **Presentation** — hero copy, featured categories, section ordering/visibility, publish policy toggle.
- **Pipeline** — last-run status, per-source record counts, trigger a manual run.

## 7. Deployment & docs

- `docker-compose.yml`: `web`, `pipeline-cron` (supercronic, Sunday 06:00 UTC), `caddy`. One shared `./data` volume. `.env` for SMTP, domain, secrets.
- Windows dev: `npm run dev` + `python -m pipeline.run` natively against the same `data/app.db`; compose optional via Docker Desktop.
- Homelab: `git clone && cp .env.example .env && docker compose up -d`.
- README documents cloud sizing (the whole stack idles well under 1 GB RAM; pipeline burst is network-bound):

| Tier | AWS | GCP | Azure | ~$/mo |
|---|---|---|---|---|
| Minimum | t3.micro (2 vCPU, 1 GB) | e2-micro (2 vCPU, 1 GB) | B1s (1 vCPU, 1 GB) | 7–10 |
| Recommended | t3.small (2 vCPU, 2 GB) | e2-small (2 vCPU, 2 GB) | B2ats_v2 / B1ms (2 GB) | 15–20 |

20 GB disk either way; SQLite backup = nightly file copy of `data/`. (Exact prices verified at build time for the README.)

## 8. Build order

1. **Scaffold + schema** — repo layout, Next.js app, Drizzle schema, compose files, MIT LICENSE. Fresh empty database; a seed script creates the first admin user.
2. **Pipeline port** — collectors/classifier/QA moved over; output targets new schema with `pending_review` + `review_items`.
3. **Auth** — users, password + email-OTP login, roles, middleware, admin user management.
4. **Public one-pager + methodology** — hero, cards, detail drawer, explorer, trends.
5. **Reviewer tool** — queue, editor, merge, QA findings, audit log.
6. **Admin presentation settings + polish** — settings, empty states, mobile pass.
7. **Verification** — pipeline run against live SEC/RSS, auth flows tested, reviewer round-trip (validate/edit/invalidate → public reflects it), README install tested via compose.

Each phase lands runnable; the site is demoable from phase 4 onward.

## Resolved decisions

- **Existing data:** fresh start — no POC data migrated. First pipeline run seeds the review queue.
- **Public sign-up:** invite-only; admin creates accounts. Public never needs an account to view.
- **License:** MIT (permissive; swap later if needed).
