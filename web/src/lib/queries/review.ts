import { db } from "@/lib/db";
import type {
  Article,
  Company,
  Filing,
  PipelineRun,
  ReviewItem,
  ReviewItemState,
  ReviewItemType,
  Revision,
  TechTag,
} from "@/lib/types";

// ---------------------------------------------------------------------------
// Queue dashboard
// ---------------------------------------------------------------------------

export interface QueueRow {
  id: number;
  type: ReviewItemType;
  company_id: number | null;
  other_company_id: number | null;
  payload: string | null;
  state: ReviewItemState;
  assigned_to: number | null;
  assignee_email: string | null;
  created_at: string;
  company_name: string | null;
  company_state: string | null;
  company_focus: string | null;
  company_type: string | null; // entity_type
  company_status: string | null;
}

export interface QueueFilters {
  type?: string;
  state?: string;
  search?: string;
}

export function countsByType(): { type: ReviewItemType; n: number }[] {
  return db
    .prepare(
      `SELECT type, COUNT(*) AS n FROM review_items WHERE state = 'open' GROUP BY type`
    )
    .all() as { type: ReviewItemType; n: number }[];
}

export function countsByState(): { state: ReviewItemState; n: number }[] {
  return db
    .prepare(`SELECT state, COUNT(*) AS n FROM review_items GROUP BY state`)
    .all() as { state: ReviewItemState; n: number }[];
}

export function listQueue(filters: QueueFilters): QueueRow[] {
  const clauses: string[] = [];
  const params: Record<string, unknown> = {};

  if (filters.type) {
    clauses.push("ri.type = @type");
    params.type = filters.type;
  }
  if (filters.state) {
    clauses.push("ri.state = @state");
    params.state = filters.state;
  } else {
    // Default view: open items only, unless a state filter is explicitly set.
    clauses.push("ri.state = 'open'");
  }
  if (filters.search) {
    clauses.push("c.name_display LIKE @search");
    params.search = `%${filters.search}%`;
  }

  const where = clauses.length ? `WHERE ${clauses.join(" AND ")}` : "";

  const rows = db
    .prepare(
      `SELECT ri.id, ri.type, ri.company_id, ri.other_company_id, ri.payload,
              ri.state, ri.assigned_to, ri.created_at,
              c.name_display AS company_name, c.state AS company_state,
              c.focus AS company_focus, c.entity_type AS company_type,
              c.status AS company_status,
              u.email AS assignee_email
       FROM review_items ri
       LEFT JOIN companies c ON c.id = ri.company_id
       LEFT JOIN users u ON u.id = ri.assigned_to
       ${where}
       ORDER BY ri.created_at DESC`
    )
    .all(params) as QueueRow[];

  return rows;
}

export function getReviewItem(id: number): ReviewItem | undefined {
  return db.prepare(`SELECT * FROM review_items WHERE id = ?`).get(id) as
    | ReviewItem
    | undefined;
}

// ---------------------------------------------------------------------------
// Company workbench
// ---------------------------------------------------------------------------

export function getCompany(id: number): Company | undefined {
  return db.prepare(`SELECT * FROM companies WHERE id = ?`).get(id) as
    | Company
    | undefined;
}

export function getFilingsForCompany(companyId: number): Filing[] {
  return db
    .prepare(
      `SELECT * FROM filings WHERE company_id = ? ORDER BY filing_date DESC`
    )
    .all(companyId) as Filing[];
}

export function getArticlesForCompany(companyId: number): Article[] {
  return db
    .prepare(
      `SELECT * FROM articles WHERE company_id = ? ORDER BY published_at DESC`
    )
    .all(companyId) as Article[];
}

export function getTagsForCompany(companyId: number): TechTag[] {
  return db
    .prepare(
      `SELECT * FROM tech_tags WHERE company_id = ? ORDER BY origin DESC, confidence DESC`
    )
    .all(companyId) as TechTag[];
}

export interface RevisionWithUser extends Revision {
  user_email: string | null;
}

export function getRecentRevisions(
  entityType: string,
  entityId: number,
  limit = 10
): RevisionWithUser[] {
  return db
    .prepare(
      `SELECT r.*, u.email AS user_email
       FROM revisions r
       LEFT JOIN users u ON u.id = r.user_id
       WHERE r.entity_type = ? AND r.entity_id = ?
       ORDER BY r.created_at DESC, r.id DESC
       LIMIT ?`
    )
    .all(entityType, entityId, limit) as RevisionWithUser[];
}

export function getOpenReviewItemsForCompany(companyId: number): ReviewItem[] {
  return db
    .prepare(
      `SELECT * FROM review_items
       WHERE state = 'open' AND (company_id = ? OR other_company_id = ?)`
    )
    .all(companyId, companyId) as ReviewItem[];
}

export function getNameAliasCount(companyId: number): number {
  const row = db
    .prepare(`SELECT COUNT(*) AS n FROM name_aliases WHERE company_id = ?`)
    .get(companyId) as { n: number };
  return row.n;
}

// ---------------------------------------------------------------------------
// Merge tool
// ---------------------------------------------------------------------------

export interface MergeCompanyView {
  company: Company;
  filingsCount: number;
  articlesCount: number;
  tagsCount: number;
}

export function getMergeCompanyView(companyId: number): MergeCompanyView | null {
  const company = getCompany(companyId);
  if (!company) return null;

  const filingsCount = (
    db.prepare(`SELECT COUNT(*) AS n FROM filings WHERE company_id = ?`).get(companyId) as {
      n: number;
    }
  ).n;
  const articlesCount = (
    db
      .prepare(`SELECT COUNT(*) AS n FROM articles WHERE company_id = ?`)
      .get(companyId) as { n: number }
  ).n;
  const tagsCount = (
    db
      .prepare(`SELECT COUNT(*) AS n FROM tech_tags WHERE company_id = ?`)
      .get(companyId) as { n: number }
  ).n;

  return { company, filingsCount, articlesCount, tagsCount };
}

// ---------------------------------------------------------------------------
// QA / pipeline runs
// ---------------------------------------------------------------------------

export interface QaFinding {
  gate: string;
  level: string;
  message: string;
}

export function listPipelineRuns(limit = 50): PipelineRun[] {
  return db
    .prepare(`SELECT * FROM pipeline_runs ORDER BY started_at DESC LIMIT ?`)
    .all(limit) as PipelineRun[];
}

export function getPipelineRun(id: number): PipelineRun | undefined {
  return db.prepare(`SELECT * FROM pipeline_runs WHERE id = ?`).get(id) as
    | PipelineRun
    | undefined;
}

export function parseQaFindings(run: PipelineRun): QaFinding[] {
  if (!run.qa_findings) return [];
  try {
    const parsed = JSON.parse(run.qa_findings);
    return Array.isArray(parsed) ? (parsed as QaFinding[]) : [];
  } catch {
    return [];
  }
}

export function prettyStats(run: PipelineRun): string {
  if (!run.stats) return "";
  try {
    return JSON.stringify(JSON.parse(run.stats), null, 0);
  } catch {
    return run.stats;
  }
}
