import Database from "better-sqlite3";
import fs from "node:fs";
import path from "node:path";

// Resolve DATABASE_PATH relative to the repo root when a relative path is
// given: process.cwd() is web/ in dev/prod, so a web-relative default of
// "../data/app.db" resolves directly against cwd to land at
// <repo>/data/app.db — no extra ".." needed (that would overshoot to the
// parent of the repo root).
function resolveDbPath(): string {
  const raw = process.env.DATABASE_PATH || "../data/app.db";
  if (path.isAbsolute(raw)) return raw;
  return path.resolve(process.cwd(), raw);
}

function openDb(): Database.Database {
  const dbPath = resolveDbPath();
  fs.mkdirSync(path.dirname(dbPath), { recursive: true });

  const instance = new Database(dbPath);
  instance.pragma("journal_mode = WAL");
  instance.pragma("busy_timeout = 5000");
  instance.pragma("foreign_keys = ON");
  return instance;
}

// Cache on globalThis so hot-reload in dev doesn't open a new handle per
// edit (each better-sqlite3 handle holds an OS file lock).
const globalForDb = globalThis as unknown as { __db?: Database.Database };

export const db: Database.Database = globalForDb.__db ?? openDb();

if (process.env.NODE_ENV !== "production") {
  globalForDb.__db = db;
}

export function nowIso(): string {
  return new Date().toISOString();
}
