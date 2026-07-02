"use server";

import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";
import { db, nowIso } from "@/lib/db";
import { hashPassword, requireRole } from "@/lib/auth";
import { TAXONOMY } from "@/lib/taxonomy";
import type { Role, User } from "@/lib/types";

const VALID_ROLES: Role[] = ["viewer", "reviewer", "admin"];

// ---------------------------------------------------------------------------
// Users
// ---------------------------------------------------------------------------

export async function createUserAction(formData: FormData): Promise<void> {
  await requireRole("admin");

  const email = String(formData.get("email") || "").trim();
  const name = String(formData.get("name") || "").trim() || null;
  const role = String(formData.get("role") || "viewer") as Role;
  const password = String(formData.get("password") || "").trim();

  if (!email || !VALID_ROLES.includes(role)) return;

  const existing = db
    .prepare(`SELECT id FROM users WHERE email = ? COLLATE NOCASE`)
    .get(email) as { id: number } | undefined;
  if (existing) return;

  const passwordHash = password ? await hashPassword(password) : null;

  db.prepare(
    `INSERT INTO users (email, name, password_hash, role, disabled, created_at)
     VALUES (?, ?, ?, ?, 0, ?)`
  ).run(email, name, passwordHash, role, nowIso());

  revalidatePath("/admin/users");
  redirect("/admin/users");
}

export async function updateRoleAction(formData: FormData): Promise<void> {
  const admin = await requireRole("admin");
  const userId = Number(formData.get("userId"));
  const role = String(formData.get("role") || "") as Role;
  if (!userId || !VALID_ROLES.includes(role)) return;

  if (userId === admin.id && role !== "admin") {
    // Prevent an admin from demoting themselves.
    return;
  }

  db.prepare(`UPDATE users SET role = ? WHERE id = ?`).run(role, userId);
  revalidatePath("/admin/users");
}

export async function toggleDisabledAction(formData: FormData): Promise<void> {
  const admin = await requireRole("admin");
  const userId = Number(formData.get("userId"));
  const disable = String(formData.get("disable")) === "1";
  if (!userId) return;

  if (userId === admin.id && disable) {
    // Prevent an admin from disabling themselves.
    return;
  }

  db.prepare(`UPDATE users SET disabled = ? WHERE id = ?`).run(disable ? 1 : 0, userId);
  revalidatePath("/admin/users");
}

export async function resetPasswordAction(formData: FormData): Promise<void> {
  await requireRole("admin");
  const userId = Number(formData.get("userId"));
  const password = String(formData.get("password") || "").trim();
  if (!userId || !password) return;

  const passwordHash = await hashPassword(password);
  db.prepare(`UPDATE users SET password_hash = ? WHERE id = ?`).run(passwordHash, userId);
  revalidatePath("/admin/users");
}

// ---------------------------------------------------------------------------
// Settings
// ---------------------------------------------------------------------------

const SETTINGS_KEYS = [
  "hero_title",
  "hero_subtitle",
  "publish_policy",
  "show_trends",
  "cards_per_section",
  "featured_categories",
] as const;

export async function saveSettingsAction(formData: FormData): Promise<void> {
  await requireRole("admin");

  const heroTitle = String(formData.get("hero_title") || "").trim();
  const heroSubtitle = String(formData.get("hero_subtitle") || "").trim();
  const publishPolicy = String(formData.get("publish_policy") || "fail_closed");
  const showTrends = formData.get("show_trends") ? "1" : "0";
  const cardsPerSection = String(Number(formData.get("cards_per_section") || 12));
  const featuredCategories = formData
    .getAll("featured_categories")
    .map(String)
    .filter((c) => (TAXONOMY as readonly string[]).includes(c));

  const values: Record<(typeof SETTINGS_KEYS)[number], string> = {
    hero_title: heroTitle,
    hero_subtitle: heroSubtitle,
    publish_policy: publishPolicy === "auto_badge" ? "auto_badge" : "fail_closed",
    show_trends: showTrends,
    cards_per_section: cardsPerSection,
    featured_categories: JSON.stringify(featuredCategories),
  };

  const existing = db.prepare(`SELECT key, value FROM site_settings`).all() as {
    key: string;
    value: string;
  }[];
  const existingMap = Object.fromEntries(existing.map((r) => [r.key, r.value]));

  const txn = db.transaction(() => {
    for (const key of SETTINGS_KEYS) {
      const newValue = values[key];
      if (existingMap[key] === newValue) continue;
      db.prepare(
        `INSERT INTO site_settings (key, value) VALUES (?, ?)
         ON CONFLICT (key) DO UPDATE SET value = excluded.value`
      ).run(key, newValue);
    }
  });
  txn();

  revalidatePath("/admin/settings");
  redirect("/admin/settings");
}
