import { db } from "@/lib/db";
import type { PipelineRun, Role, SiteSetting, User } from "@/lib/types";

// ---------------------------------------------------------------------------
// Landing counts
// ---------------------------------------------------------------------------

export function countUsersByRole(): { role: Role; n: number }[] {
  return db
    .prepare(`SELECT role, COUNT(*) AS n FROM users GROUP BY role`)
    .all() as { role: Role; n: number }[];
}

export function countCompaniesByStatus(): { status: string; n: number }[] {
  return db
    .prepare(`SELECT status, COUNT(*) AS n FROM companies GROUP BY status`)
    .all() as { status: string; n: number }[];
}

export function countOpenReviewItems(): number {
  const row = db
    .prepare(`SELECT COUNT(*) AS n FROM review_items WHERE state = 'open'`)
    .get() as { n: number };
  return row.n;
}

// ---------------------------------------------------------------------------
// Users
// ---------------------------------------------------------------------------

export function listUsers(): User[] {
  return db.prepare(`SELECT * FROM users ORDER BY created_at DESC`).all() as User[];
}

export function getUser(id: number): User | undefined {
  return db.prepare(`SELECT * FROM users WHERE id = ?`).get(id) as User | undefined;
}

export function getUserByEmail(email: string): User | undefined {
  return db
    .prepare(`SELECT * FROM users WHERE email = ? COLLATE NOCASE`)
    .get(email) as User | undefined;
}

// ---------------------------------------------------------------------------
// Settings
// ---------------------------------------------------------------------------

export function getAllSettings(): Record<string, string> {
  const rows = db.prepare(`SELECT key, value FROM site_settings`).all() as SiteSetting[];
  return Object.fromEntries(rows.map((r) => [r.key, r.value]));
}

// ---------------------------------------------------------------------------
// Pipeline
// ---------------------------------------------------------------------------

export function listPipelineRunsForAdmin(limit = 50): PipelineRun[] {
  return db
    .prepare(`SELECT * FROM pipeline_runs ORDER BY started_at DESC LIMIT ?`)
    .all(limit) as PipelineRun[];
}
