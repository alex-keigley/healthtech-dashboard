// Applies db/migrations/*.sql to the shared SQLite database, in order,
// recording each applied file in _migrations so re-runs are no-ops.
import "dotenv/config";
import { config as loadEnv } from "dotenv";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import Database from "better-sqlite3";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const webRoot = path.resolve(__dirname, ".."); // web/
const repoRoot = path.resolve(webRoot, ".."); // repo root

// Also load ../.env explicitly (repo root), in case cwd isn't web/.
loadEnv({ path: path.join(repoRoot, ".env") });

const rawDbPath = process.env.DATABASE_PATH || "../data/app.db";
const dbPath = path.isAbsolute(rawDbPath)
  ? rawDbPath
  : path.resolve(webRoot, rawDbPath);

fs.mkdirSync(path.dirname(dbPath), { recursive: true });

const db = new Database(dbPath);
db.pragma("journal_mode = WAL");
db.pragma("busy_timeout = 5000");
db.pragma("foreign_keys = ON");

db.exec(`
  CREATE TABLE IF NOT EXISTS _migrations (
    name TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL
  );
`);

const migrationsDir = path.join(repoRoot, "db", "migrations");
const files = fs
  .readdirSync(migrationsDir)
  .filter((f) => f.endsWith(".sql"))
  .sort();

const already = new Set(
  db.prepare("SELECT name FROM _migrations").all().map((r) => r.name)
);

let appliedCount = 0;
for (const file of files) {
  if (already.has(file)) continue;

  const sql = fs.readFileSync(path.join(migrationsDir, file), "utf8");
  const applyTx = db.transaction(() => {
    db.exec(sql);
    db.prepare(
      "INSERT INTO _migrations (name, applied_at) VALUES (?, ?)"
    ).run(file, new Date().toISOString());
  });

  applyTx();
  console.log(`Applied migration: ${file}`);
  appliedCount += 1;
}

if (appliedCount === 0) {
  console.log("No new migrations to apply.");
} else {
  console.log(`Applied ${appliedCount} migration(s). Database: ${dbPath}`);
}

db.close();
