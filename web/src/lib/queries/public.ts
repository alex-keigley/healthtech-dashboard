import { db } from "@/lib/db";
import type { Article, Company, Filing, TechTag } from "@/lib/types";

// ---------------------------------------------------------------------------
// Site settings
// ---------------------------------------------------------------------------

export function getSettings(): Record<string, string> {
  const rows = db.prepare(`SELECT key, value FROM site_settings`).all() as {
    key: string;
    value: string;
  }[];
  return rows.reduce<Record<string, string>>((acc, row) => {
    acc[row.key] = row.value;
    return acc;
  }, {});
}

function isAutoBadge(settings: Record<string, string>): boolean {
  return settings.publish_policy === "auto_badge";
}

// ---------------------------------------------------------------------------
// Visible companies (public access-control policy)
// ---------------------------------------------------------------------------

export interface VisibleCompany extends Company {
  unreviewed: boolean;
  tags: string[];
  largestRaise: number | null;
  filingCount: number;
  latestFilingDate: string | null;
  articleCount: number;
}

export function getVisibleCompanies(
  settings?: Record<string, string>
): VisibleCompany[] {
  const s = settings ?? getSettings();
  const autoBadge = isAutoBadge(s);

  const statusFilter = autoBadge
    ? `status IN ('published', 'pending_review')`
    : `status = 'published'`;

  const companies = db
    .prepare(`SELECT * FROM companies WHERE ${statusFilter} ORDER BY first_surfaced_at DESC`)
    .all() as Company[];

  if (companies.length === 0) return [];

  const ids = companies.map((c) => c.id);
  const placeholders = ids.map(() => "?").join(",");

  const tagRows = db
    .prepare(
      `SELECT company_id, category FROM tech_tags WHERE company_id IN (${placeholders})`
    )
    .all(...ids) as { company_id: number; category: string }[];

  const filingAggRows = db
    .prepare(
      `SELECT company_id,
              MAX(total_offering_amount) AS largest_raise,
              COUNT(*) AS filing_count,
              MAX(filing_date) AS latest_filing_date
       FROM filings
       WHERE company_id IN (${placeholders})
       GROUP BY company_id`
    )
    .all(...ids) as {
    company_id: number;
    largest_raise: number | null;
    filing_count: number;
    latest_filing_date: string | null;
  }[];

  const articleAggRows = db
    .prepare(
      `SELECT company_id, COUNT(*) AS article_count
       FROM articles
       WHERE company_id IN (${placeholders})
       GROUP BY company_id`
    )
    .all(...ids) as { company_id: number; article_count: number }[];

  const tagsByCompany = new Map<number, string[]>();
  for (const row of tagRows) {
    const list = tagsByCompany.get(row.company_id) ?? [];
    list.push(row.category);
    tagsByCompany.set(row.company_id, list);
  }

  const filingAggByCompany = new Map<number, (typeof filingAggRows)[number]>();
  for (const row of filingAggRows) {
    filingAggByCompany.set(row.company_id, row);
  }

  const articleAggByCompany = new Map<number, number>();
  for (const row of articleAggRows) {
    articleAggByCompany.set(row.company_id, row.article_count);
  }

  return companies.map((company) => {
    const filingAgg = filingAggByCompany.get(company.id);
    return {
      ...company,
      unreviewed: autoBadge && company.status === "pending_review",
      tags: tagsByCompany.get(company.id) ?? [],
      largestRaise: filingAgg?.largest_raise ?? null,
      filingCount: filingAgg?.filing_count ?? 0,
      latestFilingDate: filingAgg?.latest_filing_date ?? null,
      articleCount: articleAggByCompany.get(company.id) ?? 0,
    };
  });
}

// ---------------------------------------------------------------------------
// Hero stats
// ---------------------------------------------------------------------------

export interface HeroStats {
  totalCompanies: number;
  newlyFunded: number;
  newlySurfaced: number;
  newlyFounded: number;
  lastUpdated: string | null;
}

export function getHeroStats(settings?: Record<string, string>): HeroStats {
  const s = settings ?? getSettings();
  const autoBadge = isAutoBadge(s);

  const statusFilter = autoBadge
    ? `status IN ('published', 'pending_review')`
    : `status = 'published'`;

  const totalRow = db
    .prepare(`SELECT COUNT(*) AS n FROM companies WHERE ${statusFilter}`)
    .get() as { n: number };

  const snapshot = db
    .prepare(
      `SELECT new_funded_count, new_surfaced_count, new_founded_count
       FROM weekly_snapshots
       ORDER BY week_start DESC
       LIMIT 1`
    )
    .get() as
    | {
        new_funded_count: number;
        new_surfaced_count: number;
        new_founded_count: number;
      }
    | undefined;

  const lastRun = db
    .prepare(
      `SELECT finished_at FROM pipeline_runs
       WHERE status = 'succeeded'
       ORDER BY finished_at DESC
       LIMIT 1`
    )
    .get() as { finished_at: string | null } | undefined;

  return {
    totalCompanies: totalRow.n,
    newlyFunded: snapshot?.new_funded_count ?? 0,
    newlySurfaced: snapshot?.new_surfaced_count ?? 0,
    newlyFounded: snapshot?.new_founded_count ?? 0,
    lastUpdated: lastRun?.finished_at ?? null,
  };
}

// ---------------------------------------------------------------------------
// Company detail (access-controlled)
// ---------------------------------------------------------------------------

export interface CompanyDetail {
  company: Company & { unreviewed: boolean };
  filings: Filing[];
  articles: Article[];
  tags: TechTag[];
}

export function getCompanyDetail(id: number): CompanyDetail | null {
  const s = getSettings();
  const autoBadge = isAutoBadge(s);

  const company = db.prepare(`SELECT * FROM companies WHERE id = ?`).get(id) as
    | Company
    | undefined;

  if (!company) return null;

  const visible =
    company.status === "published" ||
    (autoBadge && company.status === "pending_review");

  if (!visible) return null;

  const filings = db
    .prepare(`SELECT * FROM filings WHERE company_id = ? ORDER BY filing_date DESC`)
    .all(id) as Filing[];

  const articles = db
    .prepare(`SELECT * FROM articles WHERE company_id = ? ORDER BY published_at DESC`)
    .all(id) as Article[];

  const tags = db
    .prepare(
      `SELECT * FROM tech_tags WHERE company_id = ? ORDER BY confidence DESC`
    )
    .all(id) as TechTag[];

  return {
    company: {
      ...company,
      unreviewed: autoBadge && company.status === "pending_review",
    },
    filings,
    articles,
    tags,
  };
}

// ---------------------------------------------------------------------------
// Trends
// ---------------------------------------------------------------------------

export interface TrendsData {
  filingsPerWeek: { week: string; count: number }[];
  topCategories: { category: string; count: number }[];
  companiesByState: { state: string; count: number }[];
}

function weekStartIso(d: Date): string {
  // Monday-start ISO week bucket, formatted as YYYY-MM-DD.
  const date = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()));
  const day = date.getUTCDay(); // 0 = Sunday
  const diffToMonday = day === 0 ? -6 : 1 - day;
  date.setUTCDate(date.getUTCDate() + diffToMonday);
  return date.toISOString().slice(0, 10);
}

export function getTrends(settings?: Record<string, string>): TrendsData {
  const s = settings ?? getSettings();
  const autoBadge = isAutoBadge(s);

  const statusFilter = autoBadge
    ? `status IN ('published', 'pending_review')`
    : `status = 'published'`;

  const visibleIds = (
    db.prepare(`SELECT id FROM companies WHERE ${statusFilter}`).all() as {
      id: number;
    }[]
  ).map((r) => r.id);

  if (visibleIds.length === 0) {
    return { filingsPerWeek: [], topCategories: [], companiesByState: [] };
  }

  const placeholders = visibleIds.map(() => "?").join(",");

  // --- filings per week: build a 12-week scaffold, then left-join counts ---
  const now = new Date();
  const weeks: string[] = [];
  const currentWeekStart = weekStartIso(now);
  for (let i = 11; i >= 0; i--) {
    const d = new Date(currentWeekStart);
    d.setUTCDate(d.getUTCDate() - i * 7);
    weeks.push(weekStartIso(d));
  }

  const filingDates = db
    .prepare(
      `SELECT filing_date FROM filings
       WHERE company_id IN (${placeholders}) AND filing_date IS NOT NULL`
    )
    .all(...visibleIds) as { filing_date: string }[];

  const countsByWeek = new Map<string, number>();
  const earliestWeek = weeks[0];
  for (const row of filingDates) {
    const d = new Date(row.filing_date);
    if (Number.isNaN(d.getTime())) continue;
    const wk = weekStartIso(d);
    if (wk < earliestWeek || wk > weeks[weeks.length - 1]) continue;
    countsByWeek.set(wk, (countsByWeek.get(wk) ?? 0) + 1);
  }

  const filingsPerWeek = weeks.map((week) => ({
    week,
    count: countsByWeek.get(week) ?? 0,
  }));

  // --- top categories: distinct company count per category ---
  const categoryRows = db
    .prepare(
      `SELECT category, COUNT(DISTINCT company_id) AS count
       FROM tech_tags
       WHERE company_id IN (${placeholders})
       GROUP BY category
       ORDER BY count DESC
       LIMIT 8`
    )
    .all(...visibleIds) as { category: string; count: number }[];

  // --- top states ---
  const stateRows = db
    .prepare(
      `SELECT state, COUNT(*) AS count
       FROM companies
       WHERE id IN (${placeholders}) AND state IS NOT NULL AND state != ''
       GROUP BY state
       ORDER BY count DESC
       LIMIT 10`
    )
    .all(...visibleIds) as { state: string; count: number }[];

  return {
    filingsPerWeek,
    topCategories: categoryRows,
    companiesByState: stateRows,
  };
}
