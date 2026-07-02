# Methodology

This is the public-facing methodology document for the Healthtech Startup
Dashboard — built to be credible with healthcare IT professionals,
executives, and students. Every decision here is in service of that
audience.

If you're evaluating the dashboard, this is the document to read first.

---

## Scope

- **Geography:** United States. National coverage; no geographic filter.
- **Sector:** US healthcare-technology companies, broadly construed — EHR /
  clinical IT, digital health, biotech, medical devices, diagnostics,
  telehealth, healthtech-adjacent services. The technology taxonomy
  (below) is the specific lens we use to tag companies.
- **Audience:** healthcare IT professionals, executives, and students.
- **Update cadence:** weekly, via an automated pipeline run.

## The three "new" signals

Different audiences care about different cuts of "new," so the dashboard
tracks three independent weekly counts rather than collapsing them into
one definition:

- **Newly funded:** companies with a Form D filing this week. Filing date
  is a strong proxy for when a private company actually raised capital
  (the SEC requires the filing within 15 days of first sale).
- **Newly surfaced:** companies we first observed in any source this week.
  This is our own water-mark; it drifts as the source stack grows.
- **Newly founded:** companies whose incorporation year is the current
  year AND whose first filing is in the window. An imperfect proxy —
  true founding dates aren't available in most free sources — but useful
  as a "brand-new and already funded" signal.

Counts are independent on purpose. A company can be "newly surfaced" to
us without being newly founded or newly funded; that's a feature, not
a bug.

## Sources

Free and open only. No paid APIs, no web scraping of paywalled content,
no ToS violations.

### Primary — Tier A

- **SEC EDGAR Form D filings** (`data.sec.gov`) — private-company capital
  raises under Regulation D. Filtered to five healthcare industry groups:
  *Biotechnology*, *Health Insurance*, *Hospitals & Physicians*,
  *Pharmaceuticals*, *Other Health Care*. Accessed via the daily master
  index; not full-text search (which was returning 500s when we built).
- **SBIR/STTR awards** (`api.www.sbir.gov`) — federal R&D grants,
  heavily populated with HHS/NIH healthtech awardees.

### Secondary — Tier B

- **Healthtech trade news (RSS):** MobiHealthNews, Fierce Healthcare,
  Healthcare IT News, Rock Health. Articles are scanned for mentions of
  companies already in the repository; matches are attached to the
  company's record and feed the classifier.

## Company identity

Every record has a **canonical name** — lowercase, punctuation stripped,
common entity suffixes (`Inc`, `LLC`, `Corp`, `Ltd`, `PLC`…) removed —
used as the merge key. The database column `companies.name_canonical` is
`UNIQUE`; subsequent filings attach to the existing row rather than
creating a duplicate. Display names preserve original casing for the UI.

Fuzzy merge proposals (names 75–95% similar) go to the in-app review
queue rather than auto-merging.

## Technology taxonomy

Every company is tagged with zero or more categories from a fixed,
18-category list aligned with widely used industry groupings:

1. Clinical IT / EHR / workflow
2. Interoperability & data exchange
3. Patient engagement
4. Telehealth / virtual care
5. Remote patient monitoring
6. AI/ML in healthcare
7. Medical imaging / radiology AI
8. Clinical decision support
9. Revenue cycle / payer tech
10. Population health / SDoH
11. Cybersecurity & privacy
12. Precision medicine / genomics
13. Digital therapeutics
14. Healthcare operations
15. Therapeutics / drug development
16. Medical devices
17. Diagnostics
18. Behavioral / mental health

Tagging is rule-based (keyword patterns over company name, industry
group, heuristic focus label, and any attached news text). Each rule
carries a base confidence score; the highest confidence per category is
kept. Reviewers can add or remove tags manually — human tags are never
overwritten by the pipeline.

## Human review & audit trail

Nothing is published to the public dashboard until a signed-in reviewer
validates it, unless the site is running in **auto-publish-with-badge**
mode (`site_settings.publish_policy = 'auto_badge'`). In that mode,
unreviewed records are shown on the public site with a visible
"Unreviewed" badge so visitors can tell the difference; the default
posture is **fail-closed** (`publish_policy = 'fail_closed'`), meaning
unreviewed records simply don't appear at all.

Review happens in an in-app reviewer tool, not via GitHub pull requests.
Authenticated reviewers (`role = 'reviewer'` or `role = 'admin'`) work a
queue of items the pipeline couldn't resolve confidently:

- **Untagged companies** — the classifier produced zero tags. The
  reviewer either confirms the company is genuinely non-specific or adds
  a tag manually.
- **Low-confidence classifications** — the best rule that fired did so
  below the confidence threshold. The reviewer confirms or corrects it.
- **Fuzzy-match pairs** — two records with 75–95% name similarity. If
  they're the same entity, the reviewer merges them.

For each company, a reviewer can **validate**, **edit**, or **invalidate**
the record. Every one of those actions — along with pipeline-driven
edits — is written to an append-only `revisions` table capturing entity
type, entity id, action, field, old value, new value, the acting user
(`NULL` for pipeline-driven changes), and a timestamp. This gives every
field on every company a full, queryable provenance history rather than
relying on commit-log archaeology.

Biasing toward "hold for review" over "auto-publish" is deliberate.
A healthcare-IT audience will lose trust fast if low-quality records
show up, and we'd rather fail-closed.

## Data-quality gates

Each weekly pipeline run produces findings from automated gates, recorded
on the run itself (`pipeline_runs.qa_findings`) and surfaced to reviewers
for acknowledgement:

- **Spike check** — filings this week vs. trailing 12-week mean (2σ
  threshold). A week that's dramatically bigger than normal might be a
  data-ingest regression, not real.
- **Orphan-tag check** — fraction of companies with zero technology tags.
  Persistent orphans mean the classifier is missing a rule.
- **Stale-source check** — any source returning zero records for two+
  consecutive weeks, which suggests a feed broke silently.
- **URL-sample check** — a random sample of filing URLs is HEAD-checked
  for 4xx/5xx to catch link rot.

## Corrections and provenance

- Every company record links back to the exact filings and articles
  that contributed to it. Dashboard users can click through to the SEC
  or news source directly.
- Corrections come from signed-in reviewers (`role = 'reviewer'` or
  `role = 'admin'`) working in the reviewer tool; every edit, validation,
  and invalidation is provenance-tracked in the `revisions` table.
- If a company pivots out of healthcare or shuts down, the record is
  archived with a reason — never silently deleted.

## Known limitations

- **Form D has no business description.** We infer a coarse "likely
  focus" label from the company name (e.g. a name containing
  *Therapeutics* → drug development) until a reviewer or a richer source
  (news article, SBIR abstract) supplies a real one.
- **Industry group is self-reported.** Pure digital-health software
  startups that file under *Technology* rather than a healthcare
  industry group are missed by Form D filtering.
- **Non-Reg-D raises aren't captured.** Reg A, Reg CF, and equity
  crowdfunding are separate filing paths we don't currently ingest.
- **News attachment rate is currently low** for small Form D filers —
  trade press covers large incumbents more than just-funded startups.
- **Incorporation dates are not available** for most companies, so the
  "newly founded" count is an imperfect proxy.
- **Coverage is best-effort, not exhaustive.** This is not a
  comprehensive registry of every US healthtech company — it's a
  weekly sample built from free, public sources.
- **Classification confidence varies** by category and by how much
  text (name, industry group, news coverage) is available for a given
  company.

## Licensing

All data presented here comes from public US government filings and
publicly-distributed RSS feeds. The methodology, code, and derived
tagging are published under the MIT License — see [LICENSE](LICENSE).
