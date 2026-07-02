import Link from "next/link";
import { notFound } from "next/navigation";
import Card from "@/components/Card";
import StatusBadge from "@/components/StatusBadge";
import { TAXONOMY } from "@/lib/taxonomy";
import {
  getArticlesForCompany,
  getCompany,
  getFilingsForCompany,
  getNameAliasCount,
  getRecentRevisions,
  getTagsForCompany,
} from "@/lib/queries/review";
import {
  addTagAction,
  invalidateCompanyAction,
  removeTagAction,
  revertToPendingAction,
  saveCompanyEdits,
  validateCompanyAction,
} from "@/app/review/actions";

export const dynamic = "force-dynamic";

function fmtMoney(n: number | null): string {
  if (n === null || n === undefined) return "—";
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(n);
}

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  return iso.slice(0, 10);
}

function humanizeRevision(field: string | null, action: string): string {
  if (action === "tag_add") return "added tag";
  if (action === "tag_remove") return "removed tag";
  if (action === "validate") return "validated";
  if (action === "invalidate") return "invalidated";
  if (action === "merge") return `merge (${field ?? ""})`;
  if (field) return `edited ${field}`;
  return action;
}

export default async function CompanyWorkbenchPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const companyId = Number(id);
  const company = getCompany(companyId);
  if (!company) notFound();

  const filings = getFilingsForCompany(companyId);
  const articles = getArticlesForCompany(companyId);
  const tags = getTagsForCompany(companyId);
  const revisions = getRecentRevisions("company", companyId, 10);
  const aliasCount = getNameAliasCount(companyId);
  const currentCategories = new Set(tags.map((t) => t.category));
  const availableToAdd = TAXONOMY.filter((c) => !currentCategories.has(c));

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold" style={{ color: "var(--color-text)" }}>
            {company.name_display}
          </h2>
          <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
            {company.name_canonical} · {aliasCount} alias{aliasCount === 1 ? "" : "es"}
          </p>
        </div>
        <StatusBadge status={company.status} />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* EVIDENCE */}
        <Card title="Evidence" className="lg:col-span-1">
          <div className="flex flex-col gap-4 text-sm">
            <div>
              <h3 className="font-medium" style={{ color: "var(--color-text)" }}>
                Filings ({filings.length})
              </h3>
              {filings.length === 0 && (
                <p style={{ color: "var(--color-text-muted)" }}>None on record.</p>
              )}
              <ul className="mt-1 flex flex-col gap-2">
                {filings.map((f) => (
                  <li key={f.accession} className="border-b pb-2" style={{ borderColor: "var(--color-border)" }}>
                    <div>{fmtDate(f.filing_date)} · {fmtMoney(f.total_offering_amount)}</div>
                    <div style={{ color: "var(--color-text-muted)" }}>{f.source}</div>
                    {f.filing_url && (
                      <a href={f.filing_url} target="_blank" rel="noreferrer">
                        SEC filing ↗
                      </a>
                    )}
                  </li>
                ))}
              </ul>
            </div>

            <div>
              <h3 className="font-medium" style={{ color: "var(--color-text)" }}>
                Articles ({articles.length})
              </h3>
              {articles.length === 0 && (
                <p style={{ color: "var(--color-text-muted)" }}>None on record.</p>
              )}
              <ul className="mt-1 flex flex-col gap-2">
                {articles.map((a) => (
                  <li key={a.id} className="border-b pb-2" style={{ borderColor: "var(--color-border)" }}>
                    <a href={a.url} target="_blank" rel="noreferrer" className="font-medium">
                      {a.title}
                    </a>
                    <div style={{ color: "var(--color-text-muted)" }}>
                      {a.source} · {fmtDate(a.published_at)}
                    </div>
                  </li>
                ))}
              </ul>
            </div>

            <div>
              <h3 className="font-medium" style={{ color: "var(--color-text)" }}>
                Description source
              </h3>
              <p style={{ color: "var(--color-text-muted)" }}>
                {company.description_source || "—"}
              </p>
              {company.description_url && (
                <a href={company.description_url} target="_blank" rel="noreferrer">
                  Source link ↗
                </a>
              )}
            </div>

            <div>
              <h3 className="font-medium" style={{ color: "var(--color-text)" }}>
                Provenance
              </h3>
              <p style={{ color: "var(--color-text-muted)" }}>
                First surfaced {fmtDate(company.first_surfaced_at)} · First funded{" "}
                {fmtDate(company.first_funded_at)} · Last updated {fmtDate(company.last_updated_at)}
              </p>
              {company.reviewed_at && (
                <p style={{ color: "var(--color-text-muted)" }}>
                  Reviewed {fmtDate(company.reviewed_at)}
                </p>
              )}
              {company.invalidation_reason && (
                <p style={{ color: "var(--color-danger)" }}>
                  Invalidation reason: {company.invalidation_reason}
                </p>
              )}
            </div>

            <div>
              <h3 className="font-medium" style={{ color: "var(--color-text)" }}>
                Recent revisions
              </h3>
              {revisions.length === 0 && (
                <p style={{ color: "var(--color-text-muted)" }}>No revisions yet.</p>
              )}
              <ul className="mt-1 flex flex-col gap-1">
                {revisions.map((r) => (
                  <li key={r.id} style={{ color: "var(--color-text-muted)" }}>
                    {fmtDate(r.created_at)} — {humanizeRevision(r.field, r.action)}
                    {r.field && r.action === "edit" ? `: "${r.old_value ?? ""}" → "${r.new_value ?? ""}"` : ""}
                    {" "}
                    by {r.user_email || "pipeline"}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </Card>

        {/* EDIT FORM */}
        <Card title="Edit" className="lg:col-span-1">
          <form action={saveCompanyEdits} className="flex flex-col gap-3 text-sm">
            <input type="hidden" name="companyId" value={company.id} />

            <label className="flex flex-col gap-1">
              Display name
              <input
                type="text"
                name="name_display"
                defaultValue={company.name_display}
                className="rounded-md border px-2 py-1"
                style={{ borderColor: "var(--color-border)" }}
              />
            </label>

            <label className="flex flex-col gap-1">
              Focus
              <input
                type="text"
                name="focus"
                defaultValue={company.focus ?? ""}
                className="rounded-md border px-2 py-1"
                style={{ borderColor: "var(--color-border)" }}
              />
            </label>

            <label className="flex flex-col gap-1">
              Description
              <textarea
                name="description"
                defaultValue={company.description ?? ""}
                rows={5}
                className="rounded-md border px-2 py-1"
                style={{ borderColor: "var(--color-border)" }}
              />
            </label>

            <label className="flex flex-col gap-1">
              Website
              <input
                type="text"
                name="website"
                defaultValue={company.website ?? ""}
                className="rounded-md border px-2 py-1"
                style={{ borderColor: "var(--color-border)" }}
              />
            </label>

            <label className="flex flex-col gap-1">
              State
              <input
                type="text"
                name="state"
                defaultValue={company.state ?? ""}
                maxLength={2}
                className="rounded-md border px-2 py-1 uppercase"
                style={{ borderColor: "var(--color-border)" }}
              />
            </label>

            <label className="flex flex-col gap-1">
              Year of incorporation
              <input
                type="text"
                name="year_of_inc"
                defaultValue={company.year_of_inc ?? ""}
                className="rounded-md border px-2 py-1"
                style={{ borderColor: "var(--color-border)" }}
              />
            </label>

            <label className="flex flex-col gap-1">
              Industry group
              <input
                type="text"
                name="industry_group"
                defaultValue={company.industry_group ?? ""}
                className="rounded-md border px-2 py-1"
                style={{ borderColor: "var(--color-border)" }}
              />
            </label>

            <button
              type="submit"
              className="mt-2 rounded-md px-3 py-2 text-sm font-medium"
              style={{ background: "var(--color-primary)", color: "var(--color-primary-contrast)" }}
            >
              Save edits
            </button>
          </form>
        </Card>

        {/* TAGS + ACTIONS */}
        <div className="flex flex-col gap-6 lg:col-span-1">
          <Card title="Tags">
            <ul className="flex flex-col gap-2 text-sm">
              {tags.map((t) => (
                <li key={t.category} className="flex items-center justify-between gap-2 border-b pb-2" style={{ borderColor: "var(--color-border)" }}>
                  <div className="flex flex-col">
                    <span>{t.category}</span>
                    <span className="flex gap-2 text-xs" style={{ color: "var(--color-text-muted)" }}>
                      <span
                        className="rounded-full px-2 py-0.5"
                        style={{
                          background: t.origin === "human" ? "#ccfbf1" : "#e5e7eb",
                          color: t.origin === "human" ? "#0f766e" : "#374151",
                        }}
                      >
                        {t.origin}
                      </span>
                      <span>conf {t.confidence.toFixed(2)}</span>
                    </span>
                  </div>
                  <form action={removeTagAction}>
                    <input type="hidden" name="companyId" value={company.id} />
                    <input type="hidden" name="category" value={t.category} />
                    <button
                      type="submit"
                      className="rounded-md border px-2 py-1 text-xs font-medium"
                      style={{ borderColor: "var(--color-border)", color: "var(--color-danger)" }}
                    >
                      Remove
                    </button>
                  </form>
                </li>
              ))}
              {tags.length === 0 && (
                <li style={{ color: "var(--color-text-muted)" }}>No tags yet.</li>
              )}
            </ul>

            {availableToAdd.length > 0 && (
              <form action={addTagAction} className="mt-3 flex gap-2">
                <input type="hidden" name="companyId" value={company.id} />
                <select
                  name="category"
                  className="flex-1 rounded-md border px-2 py-1 text-sm"
                  style={{ borderColor: "var(--color-border)" }}
                  required
                  defaultValue=""
                >
                  <option value="" disabled>
                    Add tag…
                  </option>
                  {availableToAdd.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
                <button
                  type="submit"
                  className="rounded-md px-3 py-1 text-sm font-medium"
                  style={{ background: "var(--color-primary)", color: "var(--color-primary-contrast)" }}
                >
                  Add
                </button>
              </form>
            )}
          </Card>

          <Card title="Actions">
            <div className="flex flex-col gap-3 text-sm">
              <form action={validateCompanyAction}>
                <input type="hidden" name="companyId" value={company.id} />
                <button
                  type="submit"
                  className="w-full rounded-md px-3 py-2 font-medium"
                  style={{ background: "var(--color-success)", color: "#fff" }}
                >
                  Validate → publish
                </button>
              </form>

              <form action={invalidateCompanyAction} className="flex flex-col gap-2">
                <input type="hidden" name="companyId" value={company.id} />
                <textarea
                  name="reason"
                  placeholder="Reason for invalidation (required)"
                  required
                  rows={2}
                  className="rounded-md border px-2 py-1"
                  style={{ borderColor: "var(--color-border)" }}
                />
                <button
                  type="submit"
                  className="w-full rounded-md px-3 py-2 font-medium"
                  style={{ background: "var(--color-danger)", color: "#fff" }}
                >
                  Invalidate
                </button>
              </form>

              <form action={revertToPendingAction}>
                <input type="hidden" name="companyId" value={company.id} />
                <button
                  type="submit"
                  className="w-full rounded-md border px-3 py-2 font-medium"
                  style={{ borderColor: "var(--color-border)", color: "var(--color-text)" }}
                >
                  Revert to pending
                </button>
              </form>
            </div>
          </Card>

          <Link href="/review" className="text-sm" style={{ color: "var(--color-primary)" }}>
            ← Back to queue
          </Link>
        </div>
      </div>
    </div>
  );
}
