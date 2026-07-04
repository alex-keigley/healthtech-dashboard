import crypto from "node:crypto";
import bcrypt from "bcryptjs";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { db, nowIso } from "@/lib/db";
import { sendOtpEmail } from "@/lib/email";
import type { Role, User } from "@/lib/types";

const SESSION_COOKIE = "session";
const SESSION_TTL_DAYS = 30;
const OTP_TTL_MINUTES = 10;
const OTP_MAX_UNEXPIRED = 3;
const BCRYPT_ROUNDS = 12;

function sha256(value: string): string {
  return crypto.createHash("sha256").update(value).digest("hex");
}

export async function hashPassword(pw: string): Promise<string> {
  return bcrypt.hash(pw, BCRYPT_ROUNDS);
}

export async function verifyPassword(pw: string, hash: string): Promise<boolean> {
  return bcrypt.compare(pw, hash);
}

export async function createSession(userId: number): Promise<void> {
  const token = crypto.randomBytes(32).toString("hex");
  const tokenHash = sha256(token);
  const now = new Date();
  const expiresAt = new Date(now.getTime() + SESSION_TTL_DAYS * 24 * 60 * 60 * 1000);

  db.prepare(
    `INSERT INTO sessions (token_hash, user_id, expires_at, created_at)
     VALUES (?, ?, ?, ?)`
  ).run(tokenHash, userId, expiresAt.toISOString(), nowIso());

  const cookieStore = await cookies();
  cookieStore.set(SESSION_COOKIE, token, {
    httpOnly: true,
    // Secure cookies only when the site is actually served over HTTPS —
    // browsers drop Secure cookies on plain-HTTP origins (except localhost),
    // which breaks login when testing via bare IP before TLS is set up.
    secure: (process.env.SITE_URL ?? "").startsWith("https://"),
    sameSite: "lax",
    path: "/",
    expires: expiresAt,
  });
}

export async function destroySession(): Promise<void> {
  const cookieStore = await cookies();
  const token = cookieStore.get(SESSION_COOKIE)?.value;

  if (token) {
    db.prepare("DELETE FROM sessions WHERE token_hash = ?").run(sha256(token));
  }

  cookieStore.delete(SESSION_COOKIE);
}

export async function getSessionUser(): Promise<User | null> {
  const cookieStore = await cookies();
  const token = cookieStore.get(SESSION_COOKIE)?.value;
  if (!token) return null;

  const tokenHash = sha256(token);
  const row = db
    .prepare(
      `SELECT users.* FROM sessions
       JOIN users ON users.id = sessions.user_id
       WHERE sessions.token_hash = ?
         AND sessions.expires_at > ?
         AND users.disabled = 0`
    )
    .get(tokenHash, nowIso()) as User | undefined;

  return row ?? null;
}

function roleSatisfies(userRole: Role, required: "reviewer" | "admin"): boolean {
  if (userRole === "admin") return true;
  return userRole === required;
}

export async function requireRole(role: "reviewer" | "admin"): Promise<User> {
  const user = await getSessionUser();
  if (!user) {
    redirect("/login");
  }
  if (!roleSatisfies(user.role, role)) {
    redirect("/");
  }
  return user;
}

export async function requestOtp(email: string): Promise<void> {
  const user = db
    .prepare("SELECT * FROM users WHERE email = ? COLLATE NOCASE AND disabled = 0")
    .get(email) as User | undefined;

  // Invite-only: never reveal whether the email exists. Silently no-op
  // for unknown/disabled accounts instead of erroring.
  if (!user) return;

  const unexpiredCount = db
    .prepare(
      `SELECT COUNT(*) AS n FROM otp_codes
       WHERE user_id = ? AND used = 0 AND expires_at > ?`
    )
    .get(user.id, nowIso()) as { n: number };

  if (unexpiredCount.n >= OTP_MAX_UNEXPIRED) return;

  const code = crypto.randomInt(0, 1_000_000).toString().padStart(6, "0");
  const codeHash = sha256(code);
  const expiresAt = new Date(Date.now() + OTP_TTL_MINUTES * 60 * 1000).toISOString();

  db.prepare(
    `INSERT INTO otp_codes (user_id, code_hash, expires_at, used, created_at)
     VALUES (?, ?, ?, 0, ?)`
  ).run(user.id, codeHash, expiresAt, nowIso());

  await sendOtpEmail(user.email, code);
}

export async function verifyOtp(email: string, code: string): Promise<boolean> {
  const user = db
    .prepare("SELECT * FROM users WHERE email = ? COLLATE NOCASE AND disabled = 0")
    .get(email) as User | undefined;

  if (!user) return false;

  const codeHash = sha256(code);
  const otp = db
    .prepare(
      `SELECT * FROM otp_codes
       WHERE user_id = ? AND code_hash = ? AND used = 0 AND expires_at > ?
       ORDER BY id DESC LIMIT 1`
    )
    .get(user.id, codeHash, nowIso()) as { id: number } | undefined;

  if (!otp) return false;

  db.prepare("UPDATE otp_codes SET used = 1 WHERE id = ?").run(otp.id);
  db.prepare("UPDATE users SET last_login_at = ? WHERE id = ?").run(nowIso(), user.id);

  await createSession(user.id);
  return true;
}

export async function loginWithPassword(email: string, pw: string): Promise<boolean> {
  const user = db
    .prepare("SELECT * FROM users WHERE email = ? COLLATE NOCASE AND disabled = 0")
    .get(email) as User | undefined;

  if (!user || !user.password_hash) return false;

  const valid = await verifyPassword(pw, user.password_hash);
  if (!valid) return false;

  db.prepare("UPDATE users SET last_login_at = ? WHERE id = ?").run(nowIso(), user.id);
  await createSession(user.id);
  return true;
}
