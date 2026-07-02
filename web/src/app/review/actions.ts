"use server";

import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";
import { db, nowIso } from "@/lib/db";
import { requireRole } from "@/lib/auth";
import { TAXONOMY } from "@/lib/taxonomy";
import type { Company, ReviewItem } from "@/lib/types";

function logRevision(
  entityType: string,
  entityId: number,
  action: string,
  field: string | null,
  oldValue: string | null,
  newValue: string | null,
  userId: number
) {
  db.prepare(
    `INSERT INTO revisions (entity_type, entity_id, action, field, old_value, new_value, user_id, created_at)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?)`
  ).run(entityType, entityId, action, field, oldValue, newValue, userId, nowIso());
}

function resolveOpenReviewItems(
  companyId: number,
  note: string,
  userId: number
) {
  db.prepare(
    `UPDATE review_items
     SET state = 'resolved', resolution_note = ?, resolved_by = ?, resolved_at = ?
     WHERE state = 'open' AND (company_id = ? OR other_company_id = ?)`
  ).run(note, userId, nowIso(), companyId, companyId);
}

// ---------------------------------------------------------------------------
// Queue actions
// ---------------------------------------------------------------------------

export async function claimItemAction(formData: FormData): Promise<void> {
  const user = await requireRole("reviewer");
  const itemId = Number(formData.get("itemId"));
  if (!itemId) return;

  db.prepare(`UPDATE review_items SET assigned_to = ? WHERE id = ?`).run(
    user.id,
    itemId
  );

  revalidatePath("/review");
}

export async function dismissItemAction(formData: FormData): Promise<void> {
  const user = await requireRole("reviewer");
  const itemId = Number(formData.get("itemId"));
  const note = String(formData.get("note") || "").trim();
  if (!itemId || !note) return;

  db.prepare(
    `UPDATE review_items
     SET state = 'dismissed', resolution_note = ?, resolved_by = ?, resolved_at = ?
     WHERE id = ?`
  ).run(note, user.id, nowIso(), itemId);

  revalidatePath("/review");
}

// ---------------------------------------------------------------------------
// Company workbench
// ---------------------------------------------------------------------------

const EDITABLE_FIELDS = [
  "name_display",
  "focus",
  "description",
  "website",
  "state",
  "year_of_inc",
  "industry_group",
] as const;

export async function saveCompanyEdits(formData: FormData): Promise<void> {
  const user = await requireRole("reviewer");
  const companyId = Number(formData.get("companyId"));
  if (!companyId) return;

  const company = db
    .prepare(`SELECT * FROM companies WHERE id = ?`)
    .get(companyId) as Company | undefined;
  if (!company) return;

  const updates: Record<string, string | null> = {};
  for (const field of EDITABLE_FIELDS) {
    const raw = formData.get(field);
    const newValue = raw === null ? null : String(raw).trim() || null;
    const oldValue = (company[field as keyof Company] as string | null) ?? null;
    if (newValue !== oldValue) {
      updates[field] = newValue;
    }
  }

  if (Object.keys(updates).length === 0) {
    redirect(`/review/company/${companyId}`);
  }

  const txn = db.transaction(() => {
    for (const [field, newValue] of Object.entries(updates)) {
      const oldValue = (company[field as keyof Company] as string | null) ?? null;
      logRevision("company", companyId, "edit", field, oldValue, newValue, user.id);
    }

    const setClauses = Object.keys(updates)
      .map((f) => `${f} = @${f}`)
      .join(", ");
    db.prepare(
      `UPDATE companies SET ${setClauses}, last_updated_at = @last_updated_at WHERE id = @id`
    ).run({ ...updates, last_updated_at: nowIso(), id: companyId });
  });
  txn();

  revalidatePath(`/review/company/${companyId}`);
  redirect(`/review/company/${companyId}`);
}

export async function addTagAction(formData: FormData): Promise<void> {
  const user = await requireRole("reviewer");
  const companyId = Number(formData.get("companyId"));
  const category = String(formData.get("category") || "");
  if (!companyId || !TAXONOMY.includes(category as (typeof TAXONOMY)[number])) return;

  const txn = db.transaction(() => {
    db.prepare(
      `INSERT INTO tech_tags (company_id, category, confidence, origin, tagged_at)
       VALUES (?, ?, 1.0, 'human', ?)
       ON CONFLICT (company_id, category) DO UPDATE SET
         confidence = 1.0, origin = 'human', tagged_at = excluded.tagged_at`
    ).run(companyId, category, nowIso());

    logRevision("company", companyId, "tag_add", "category", null, category, user.id);
  });
  txn();

  revalidatePath(`/review/company/${companyId}`);
  redirect(`/review/company/${companyId}`);
}

export async function removeTagAction(formData: FormData): Promise<void> {
  const user = await requireRole("reviewer");
  const companyId = Number(formData.get("companyId"));
  const category = String(formData.get("category") || "");
  if (!companyId || !category) return;

  const txn = db.transaction(() => {
    db.prepare(
      `DELETE FROM tech_tags WHERE company_id = ? AND category = ?`
    ).run(companyId, category);

    logRevision("company", companyId, "tag_remove", "category", category, null, user.id);
  });
  txn();

  revalidatePath(`/review/company/${companyId}`);
  redirect(`/review/company/${companyId}`);
}

export async function validateCompanyAction(formData: FormData): Promise<void> {
  const user = await requireRole("reviewer");
  const companyId = Number(formData.get("companyId"));
  if (!companyId) return;

  const company = db
    .prepare(`SELECT * FROM companies WHERE id = ?`)
    .get(companyId) as Company | undefined;
  if (!company) return;

  const txn = db.transaction(() => {
    db.prepare(
      `UPDATE companies
       SET status = 'published', reviewed_by = ?, reviewed_at = ?, last_updated_at = ?
       WHERE id = ?`
    ).run(user.id, nowIso(), nowIso(), companyId);

    logRevision(
      "company",
      companyId,
      "validate",
      "status",
      company.status,
      "published",
      user.id
    );

    resolveOpenReviewItems(companyId, "validated", user.id);
  });
  txn();

  revalidatePath(`/review/company/${companyId}`);
  revalidatePath("/review");
  redirect(`/review/company/${companyId}`);
}

export async function invalidateCompanyAction(formData: FormData): Promise<void> {
  const user = await requireRole("reviewer");
  const companyId = Number(formData.get("companyId"));
  const reason = String(formData.get("reason") || "").trim();
  if (!companyId || !reason) return;

  const company = db
    .prepare(`SELECT * FROM companies WHERE id = ?`)
    .get(companyId) as Company | undefined;
  if (!company) return;

  const txn = db.transaction(() => {
    db.prepare(
      `UPDATE companies
       SET status = 'invalidated', reviewed_by = ?, reviewed_at = ?, invalidation_reason = ?, last_updated_at = ?
       WHERE id = ?`
    ).run(user.id, nowIso(), reason, nowIso(), companyId);

    logRevision(
      "company",
      companyId,
      "invalidate",
      "status",
      company.status,
      "invalidated",
      user.id
    );

    resolveOpenReviewItems(companyId, `invalidated: ${reason}`, user.id);
  });
  txn();

  revalidatePath(`/review/company/${companyId}`);
  revalidatePath("/review");
  redirect(`/review/company/${companyId}`);
}

export async function revertToPendingAction(formData: FormData): Promise<void> {
  const user = await requireRole("reviewer");
  const companyId = Number(formData.get("companyId"));
  if (!companyId) return;

  const company = db
    .prepare(`SELECT * FROM companies WHERE id = ?`)
    .get(companyId) as Company | undefined;
  if (!company) return;

  const txn = db.transaction(() => {
    db.prepare(
      `UPDATE companies
       SET status = 'pending_review', last_updated_at = ?
       WHERE id = ?`
    ).run(nowIso(), companyId);

    logRevision(
      "company",
      companyId,
      "edit",
      "status",
      company.status,
      "pending_review",
      user.id
    );
  });
  txn();

  revalidatePath(`/review/company/${companyId}`);
  revalidatePath("/review");
  redirect(`/review/company/${companyId}`);
}

// ---------------------------------------------------------------------------
// Merge tool
// ---------------------------------------------------------------------------

export async function mergeCompaniesAction(formData: FormData): Promise<void> {
  const user = await requireRole("reviewer");
  const itemId = Number(formData.get("itemId"));
  const survivorId = Number(formData.get("survivorId"));
  const loserId = Number(formData.get("loserId"));
  if (!itemId || !survivorId || !loserId || survivorId === loserId) return;

  const survivor = db
    .prepare(`SELECT * FROM companies WHERE id = ?`)
    .get(survivorId) as Company | undefined;
  const loser = db
    .prepare(`SELECT * FROM companies WHERE id = ?`)
    .get(loserId) as Company | undefined;
  if (!survivor || !loser) return;

  const txn = db.transaction(() => {
    // Survivor keeps the earliest first_funded_at / first_surfaced_at.
    const earliestFunded = earliestNonNull(
      survivor.first_funded_at,
      loser.first_funded_at
    );
    const earliestSurfaced = earliestNonNull(
      survivor.first_surfaced_at,
      loser.first_surfaced_at
    )!;

    if (earliestFunded !== survivor.first_funded_at) {
      logRevision(
        "company",
        survivorId,
        "merge",
        "first_funded_at",
        survivor.first_funded_at,
        earliestFunded,
        user.id
      );
    }
    if (earliestSurfaced !== survivor.first_surfaced_at) {
      logRevision(
        "company",
        survivorId,
        "merge",
        "first_surfaced_at",
        survivor.first_surfaced_at,
        earliestSurfaced,
        user.id
      );
    }

    db.prepare(
      `UPDATE companies
       SET first_funded_at = ?, first_surfaced_at = ?, last_updated_at = ?
       WHERE id = ?`
    ).run(earliestFunded, earliestSurfaced, nowIso(), survivorId);

    // Repoint loser's filings/articles to survivor.
    db.prepare(`UPDATE filings SET company_id = ? WHERE company_id = ?`).run(
      survivorId,
      loserId
    );
    db.prepare(`UPDATE articles SET company_id = ? WHERE company_id = ?`).run(
      survivorId,
      loserId
    );

    // Repoint loser's tech_tags to survivor, ignoring duplicates (survivor
    // already has that category — keep whichever the pk-conflict favors,
    // i.e. leave survivor's existing row and drop the loser's duplicate).
    const loserTags = db
      .prepare(`SELECT * FROM tech_tags WHERE company_id = ?`)
      .all(loserId) as { category: string; confidence: number; origin: string; tagged_at: string }[];
    for (const tag of loserTags) {
      db.prepare(
        `INSERT INTO tech_tags (company_id, category, confidence, origin, tagged_at)
         VALUES (?, ?, ?, ?, ?)
         ON CONFLICT (company_id, category) DO NOTHING`
      ).run(survivorId, tag.category, tag.confidence, tag.origin, tag.tagged_at);
    }
    db.prepare(`DELETE FROM tech_tags WHERE company_id = ?`).run(loserId);

    // Repoint loser's name_aliases to survivor, ignoring duplicates.
    const loserAliases = db
      .prepare(`SELECT * FROM name_aliases WHERE company_id = ?`)
      .all(loserId) as {
      alias_canonical: string;
      alias_display: string;
      source: string;
    }[];
    for (const alias of loserAliases) {
      db.prepare(
        `INSERT INTO name_aliases (company_id, alias_canonical, alias_display, source)
         VALUES (?, ?, ?, ?)
         ON CONFLICT (company_id, alias_canonical) DO NOTHING`
      ).run(survivorId, alias.alias_canonical, alias.alias_display, alias.source);
    }
    db.prepare(`DELETE FROM name_aliases WHERE company_id = ?`).run(loserId);

    // Record loser's own name as an alias of survivor.
    db.prepare(
      `INSERT INTO name_aliases (company_id, alias_canonical, alias_display, source)
       VALUES (?, ?, ?, 'merge')
       ON CONFLICT (company_id, alias_canonical) DO NOTHING`
    ).run(survivorId, loser.name_canonical, loser.name_display);

    // Archive the loser.
    const invalidationReason = `merged into #${survivorId}`;
    db.prepare(
      `UPDATE companies
       SET status = 'archived', invalidation_reason = ?, last_updated_at = ?
       WHERE id = ?`
    ).run(invalidationReason, nowIso(), loserId);

    logRevision(
      "company",
      loserId,
      "merge",
      "status",
      loser.status,
      "archived",
      user.id
    );
    logRevision(
      "company",
      survivorId,
      "merge",
      "merged_from",
      null,
      String(loserId),
      user.id
    );

    // Resolve the review item and any other open items referencing either
    // company (fuzzy_match rows might reference the pair in either order).
    db.prepare(
      `UPDATE review_items
       SET state = 'resolved', resolution_note = ?, resolved_by = ?, resolved_at = ?
       WHERE id = ?`
    ).run(`merged #${loserId} into #${survivorId}`, user.id, nowIso(), itemId);

    db.prepare(
      `UPDATE review_items
       SET state = 'resolved', resolution_note = ?, resolved_by = ?, resolved_at = ?
       WHERE state = 'open' AND id != ?
         AND (company_id IN (?, ?) OR other_company_id IN (?, ?))`
    ).run(
      `merged #${loserId} into #${survivorId}`,
      user.id,
      nowIso(),
      itemId,
      survivorId,
      loserId,
      survivorId,
      loserId
    );
  });
  txn();

  revalidatePath("/review");
  redirect(`/review/company/${survivorId}`);
}

function earliestNonNull(a: string | null, b: string | null): string | null {
  if (!a) return b;
  if (!b) return a;
  return a < b ? a : b;
}

export async function notSameCompanyAction(formData: FormData): Promise<void> {
  const user = await requireRole("reviewer");
  const itemId = Number(formData.get("itemId"));
  const note = String(formData.get("note") || "not the same company").trim();
  if (!itemId) return;

  db.prepare(
    `UPDATE review_items
     SET state = 'dismissed', resolution_note = ?, resolved_by = ?, resolved_at = ?
     WHERE id = ?`
  ).run(note || "not the same company", user.id, nowIso(), itemId);

  revalidatePath("/review");
  redirect("/review");
}

// ---------------------------------------------------------------------------
// QA runs
// ---------------------------------------------------------------------------

export async function acknowledgeRunAction(formData: FormData): Promise<void> {
  const user = await requireRole("reviewer");
  const runId = Number(formData.get("runId"));
  if (!runId) return;

  db.prepare(
    `UPDATE pipeline_runs SET qa_acked_by = ?, qa_acked_at = ? WHERE id = ?`
  ).run(user.id, nowIso(), runId);

  revalidatePath("/review/qa");
}
