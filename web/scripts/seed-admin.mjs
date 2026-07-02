// Upserts an admin user for first-run setup. Usage:
//   node scripts/seed-admin.mjs [email] [password]
// or via ADMIN_EMAIL / ADMIN_PASSWORD env vars (e.g. from repo-root .env).
import "dotenv/config";
import { config as loadEnv } from "dotenv";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import Database from "better-sqlite3";
import bcrypt from "bcryptjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const webRoot = path.resolve(__dirname, "..");
const repoRoot = path.resolve(webRoot, "..");

loadEnv({ path: path.join(repoRoot, ".env") });

const email = process.argv[2] || process.env.ADMIN_EMAIL;
const password = process.argv[3] || process.env.ADMIN_PASSWORD;

if (!email || !password) {
  console.error(
    "Usage: node scripts/seed-admin.mjs <email> <password>\n" +
      "(or set ADMIN_EMAIL / ADMIN_PASSWORD env vars)"
  );
  process.exit(1);
}

const rawDbPath = process.env.DATABASE_PATH || "../data/app.db";
const dbPath = path.isAbsolute(rawDbPath)
  ? rawDbPath
  : path.resolve(webRoot, rawDbPath);

fs.mkdirSync(path.dirname(dbPath), { recursive: true });

const db = new Database(dbPath);
db.pragma("journal_mode = WAL");
db.pragma("busy_timeout = 5000");
db.pragma("foreign_keys = ON");

const passwordHash = bcrypt.hashSync(password, 12);
const now = new Date().toISOString();

const existing = db
  .prepare("SELECT id FROM users WHERE email = ? COLLATE NOCASE")
  .get(email);

if (existing) {
  db.prepare(
    "UPDATE users SET password_hash = ?, role = 'admin', disabled = 0 WHERE id = ?"
  ).run(passwordHash, existing.id);
  console.log(`Updated existing user ${email} (id ${existing.id}) to role 'admin'.`);
} else {
  const info = db
    .prepare(
      `INSERT INTO users (email, name, password_hash, role, disabled, created_at)
       VALUES (?, NULL, ?, 'admin', 0, ?)`
    )
    .run(email, passwordHash, now);
  console.log(`Created admin user ${email} (id ${info.lastInsertRowid}).`);
}

db.close();
