// Ad-hoc test-data seeder for Phase 4 manual verification. Not part of the
// production pipeline — inserts a handful of realistic rows covering the
// published / pending_review / new-this-week / trends scenarios.
import Database from "better-sqlite3";

const dbPath = process.env.DATABASE_PATH || "/tmp/build/data/app.db";
const db = new Database(dbPath);
db.pragma("foreign_keys = ON");

const now = new Date();
const nowIso = now.toISOString();

function daysAgoIso(n) {
  const d = new Date(now);
  d.setDate(d.getDate() - n);
  return d.toISOString();
}

function dateOnly(iso) {
  return iso.slice(0, 10);
}

const insertCompany = db.prepare(`
  INSERT INTO companies (
    name_canonical, name_display, cik, state, year_of_inc, entity_type,
    industry_group, focus, website, description, description_source, description_url,
    first_surfaced_at, first_funded_at, last_updated_at, status, reviewed_by, reviewed_at, invalidation_reason
  ) VALUES (
    @name_canonical, @name_display, @cik, @state, @year_of_inc, @entity_type,
    @industry_group, @focus, @website, @description, @description_source, @description_url,
    @first_surfaced_at, @first_funded_at, @last_updated_at, @status, @reviewed_by, @reviewed_at, @invalidation_reason
  )
`);

const insertFiling = db.prepare(`
  INSERT INTO filings (
    accession, company_id, source, filing_date, date_of_first_sale,
    total_offering_amount, filing_url, observed_at
  ) VALUES (
    @accession, @company_id, @source, @filing_date, @date_of_first_sale,
    @total_offering_amount, @filing_url, @observed_at
  )
`);

const insertArticle = db.prepare(`
  INSERT INTO articles (company_id, source, title, url, summary, published_at, observed_at)
  VALUES (@company_id, @source, @title, @url, @summary, @published_at, @observed_at)
`);

const insertTag = db.prepare(`
  INSERT INTO tech_tags (company_id, category, confidence, origin, tagged_at)
  VALUES (@company_id, @category, @confidence, @origin, @tagged_at)
`);

const insertPipelineRun = db.prepare(`
  INSERT INTO pipeline_runs (
    started_at, finished_at, window_start, window_end, status, stats, qa_findings, qa_acked_by, qa_acked_at, log_tail
  ) VALUES (
    @started_at, @finished_at, @window_start, @window_end, @status, @stats, @qa_findings, @qa_acked_by, @qa_acked_at, @log_tail
  )
`);

const insertSnapshot = db.prepare(`
  INSERT INTO weekly_snapshots (
    week_start, new_founded_count, new_funded_count, new_surfaced_count, notes, generated_at
  ) VALUES (
    @week_start, @new_founded_count, @new_funded_count, @new_surfaced_count, @notes, @generated_at
  )
`);

const tx = db.transaction(() => {
  // 1. Published company, surfaced within last 14 days (New This Week).
  const c1 = insertCompany.run({
    name_canonical: "brightpath health ai",
    name_display: "BrightPath Health AI",
    cik: "0001999001",
    state: "MA",
    year_of_inc: "2025",
    entity_type: "Corporation",
    industry_group: "Biotechnology",
    focus: "AI-powered radiology triage for community hospitals",
    website: "https://brightpathhealth.example.com",
    description:
      "BrightPath builds AI-assisted triage tools for radiology departments, helping community hospitals prioritize urgent imaging studies.",
    description_source: "Company website",
    description_url: "https://brightpathhealth.example.com/about",
    first_surfaced_at: daysAgoIso(3),
    first_funded_at: daysAgoIso(5),
    last_updated_at: nowIso,
    status: "published",
    reviewed_by: null,
    reviewed_at: null,
    invalidation_reason: null,
  }).lastInsertRowid;

  insertFiling.run({
    accession: "0001999001-26-000001",
    company_id: c1,
    source: "SEC EDGAR",
    filing_date: dateOnly(daysAgoIso(5)),
    date_of_first_sale: dateOnly(daysAgoIso(6)),
    total_offering_amount: 5600000,
    filing_url:
      "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0001999001",
    observed_at: daysAgoIso(4),
  });

  insertTag.run({
    company_id: c1,
    category: "AI/ML in healthcare",
    confidence: 0.92,
    origin: "machine",
    tagged_at: daysAgoIso(3),
  });
  insertTag.run({
    company_id: c1,
    category: "Medical imaging / radiology AI",
    confidence: 0.88,
    origin: "machine",
    tagged_at: daysAgoIso(3),
  });

  insertArticle.run({
    company_id: c1,
    source: "MobiHealthNews",
    title: "BrightPath Health AI raises $5.6M seed to speed up radiology triage",
    url: "https://www.mobihealthnews.example.com/brightpath-seed",
    summary: "BrightPath announced a $5.6M seed round led by a healthtech-focused fund.",
    published_at: dateOnly(daysAgoIso(4)),
    observed_at: daysAgoIso(3),
  });

  // 2. Second published company, older first_surfaced_at (outside 14-day window).
  const c2 = insertCompany.run({
    name_canonical: "riverside remote care",
    name_display: "Riverside Remote Care",
    cik: "0001999002",
    state: "TX",
    year_of_inc: "2023",
    entity_type: "LLC",
    industry_group: "Other Health Care",
    focus: "Remote patient monitoring for chronic cardiac conditions",
    website: "https://riversideremotecare.example.com",
    description:
      "Riverside Remote Care provides connected-device remote monitoring programs for patients with chronic cardiac conditions.",
    description_source: "Company website",
    description_url: "https://riversideremotecare.example.com/about",
    first_surfaced_at: daysAgoIso(120),
    first_funded_at: daysAgoIso(130),
    last_updated_at: daysAgoIso(30),
    status: "published",
    reviewed_by: null,
    reviewed_at: null,
    invalidation_reason: null,
  }).lastInsertRowid;

  insertFiling.run({
    accession: "0001999002-26-000001",
    company_id: c2,
    source: "SEC EDGAR",
    filing_date: dateOnly(daysAgoIso(130)),
    date_of_first_sale: dateOnly(daysAgoIso(131)),
    total_offering_amount: 330000000,
    filing_url:
      "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0001999002",
    observed_at: daysAgoIso(129),
  });

  insertFiling.run({
    accession: "0001999002-26-000002",
    company_id: c2,
    source: "SEC EDGAR",
    filing_date: dateOnly(daysAgoIso(20)),
    date_of_first_sale: dateOnly(daysAgoIso(21)),
    total_offering_amount: 4000,
    filing_url:
      "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0001999002&type=D-A",
    observed_at: daysAgoIso(19),
  });

  insertTag.run({
    company_id: c2,
    category: "Remote patient monitoring",
    confidence: 0.95,
    origin: "human",
    tagged_at: daysAgoIso(100),
  });

  // 3. Pending-review company (tests unreviewed-badge / fail-closed gating).
  insertCompany.run({
    name_canonical: "sunrise behavioral partners",
    name_display: "Sunrise Behavioral Partners",
    cik: "0001999003",
    state: "CA",
    year_of_inc: "2026",
    entity_type: "Corporation",
    industry_group: "Other Health Care",
    focus: "Teletherapy platform for adolescent behavioral health",
    website: "https://sunrisebehavioral.example.com",
    description:
      "Sunrise Behavioral Partners operates a teletherapy platform focused on adolescent behavioral health services.",
    description_source: "Company website",
    description_url: "https://sunrisebehavioral.example.com/about",
    first_surfaced_at: daysAgoIso(1),
    first_funded_at: daysAgoIso(2),
    last_updated_at: nowIso,
    status: "pending_review",
    reviewed_by: null,
    reviewed_at: null,
    invalidation_reason: null,
  });

  // Pipeline run: succeeded, recent.
  insertPipelineRun.run({
    started_at: daysAgoIso(1),
    finished_at: daysAgoIso(1),
    window_start: dateOnly(daysAgoIso(8)),
    window_end: dateOnly(daysAgoIso(1)),
    status: "succeeded",
    stats: JSON.stringify({ new_companies: 3, filings_ingested: 4 }),
    qa_findings: JSON.stringify([]),
    qa_acked_by: null,
    qa_acked_at: null,
    log_tail: "Pipeline run completed successfully.",
  });

  // Weekly snapshot for the current week.
  const monday = new Date(now);
  const day = monday.getUTCDay();
  const diffToMonday = day === 0 ? -6 : 1 - day;
  monday.setUTCDate(monday.getUTCDate() + diffToMonday);
  insertSnapshot.run({
    week_start: dateOnly(monday.toISOString()),
    new_founded_count: 1,
    new_funded_count: 2,
    new_surfaced_count: 3,
    notes: "Test snapshot for Phase 4 verification.",
    generated_at: nowIso,
  });
});

tx();

const ids = db.prepare("SELECT id, name_display, status FROM companies").all();
console.log("Seeded companies:", JSON.stringify(ids, null, 2));

db.close();
