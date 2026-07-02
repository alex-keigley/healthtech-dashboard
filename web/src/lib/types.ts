// TypeScript row shapes mirroring db/migrations/0001_init.sql exactly.
// Nullable SQLite columns map to `T | null` (better-sqlite3 returns null,
// never undefined, for absent values).

export type Role = "viewer" | "reviewer" | "admin";

export type CompanyStatus =
  | "pending_review"
  | "published"
  | "invalidated"
  | "archived";

export type TagOrigin = "machine" | "human";

export type ReviewItemType =
  | "new_record"
  | "untagged"
  | "low_confidence"
  | "fuzzy_match";

export type ReviewItemState = "open" | "resolved" | "dismissed";

export type RevisionAction =
  | "edit"
  | "validate"
  | "invalidate"
  | "merge"
  | "create"
  | "tag_add"
  | "tag_remove";

export type PipelineRunStatus = "running" | "succeeded" | "failed";

export type PublishPolicy = "fail_closed" | "auto_badge";

export interface User {
  id: number;
  email: string;
  name: string | null;
  password_hash: string | null;
  role: Role;
  disabled: number; // SQLite boolean: 0 | 1
  created_at: string;
  last_login_at: string | null;
}

export interface Session {
  token_hash: string;
  user_id: number;
  expires_at: string;
  created_at: string;
}

export interface OtpCode {
  id: number;
  user_id: number;
  code_hash: string;
  expires_at: string;
  used: number; // 0 | 1
  created_at: string;
}

export interface Company {
  id: number;
  name_canonical: string;
  name_display: string;
  cik: string | null;
  state: string | null;
  year_of_inc: string | null;
  entity_type: string | null;
  industry_group: string | null;
  focus: string | null;
  website: string | null;
  description: string | null;
  description_source: string | null;
  description_url: string | null;
  first_surfaced_at: string;
  first_funded_at: string | null;
  last_updated_at: string;
  status: CompanyStatus;
  reviewed_by: number | null;
  reviewed_at: string | null;
  invalidation_reason: string | null;
}

export interface Filing {
  accession: string;
  company_id: number;
  source: string;
  filing_date: string | null;
  date_of_first_sale: string | null;
  total_offering_amount: number | null;
  filing_url: string | null;
  observed_at: string;
}

export interface Article {
  id: number;
  company_id: number;
  source: string;
  title: string;
  url: string;
  summary: string | null;
  published_at: string | null;
  observed_at: string;
}

export interface TechTag {
  company_id: number;
  category: string;
  confidence: number;
  origin: TagOrigin;
  tagged_at: string;
}

export interface NameAlias {
  company_id: number;
  alias_canonical: string;
  alias_display: string;
  source: string;
}

export interface WeeklySnapshot {
  week_start: string;
  new_founded_count: number;
  new_funded_count: number;
  new_surfaced_count: number;
  notes: string | null;
  generated_at: string;
}

export interface ReviewItem {
  id: number;
  type: ReviewItemType;
  company_id: number | null;
  other_company_id: number | null;
  payload: string | null; // JSON
  state: ReviewItemState;
  assigned_to: number | null;
  resolution_note: string | null;
  resolved_by: number | null;
  resolved_at: string | null;
  created_at: string;
}

export interface Revision {
  id: number;
  entity_type: string;
  entity_id: number;
  action: RevisionAction;
  field: string | null;
  old_value: string | null;
  new_value: string | null;
  user_id: number | null; // NULL = pipeline
  created_at: string;
}

export interface PipelineRun {
  id: number;
  started_at: string;
  finished_at: string | null;
  window_start: string | null;
  window_end: string | null;
  status: PipelineRunStatus;
  stats: string | null; // JSON
  qa_findings: string | null; // JSON
  qa_acked_by: number | null;
  qa_acked_at: string | null;
  log_tail: string | null;
}

export interface SiteSetting {
  key: string;
  value: string;
}
