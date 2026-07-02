import Link from "next/link";
import { notFound } from "next/navigation";
import Card from "@/components/Card";
import StatusBadge from "@/components/StatusBadge";
import { getMergeCompanyView, getReviewItem } from "@/lib/queries/review";
import { mergeCompaniesAction, notSameCompanyAction } from "@/app/review/actions";
import type { MergeCompanyView } from "@/lib/queries/review";

export const dynamic = "force-dynamic";

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  return iso.slice(0, 10);
}

function CompanyColumn({ view }: { view: MergeCompanyView }) {
  const c = view.company;
  return (
    <div className="flex flex-col gap-2 text-sm">
      <div className="flex items-center justify-between">
        <h3 className="text-base font-semibold" style={{ color: "var(--color-text)" }}>
          {c.name_display}
        </h3>
        <StatusBadge status={c.status} />
      </div>
      <p style={{ color: "var(--color-text-muted)" }}>#{c.id} · {c.name_canonical}</p>
      <dl className="flex flex-col gap-1">
        <Row label="State" value={c.state} />
        <Row label="Focus" value={c.focus} />
        <Row label="Industry group" value={c.industry_group} />
        <Row label="Entity type" value={c.entity_type} />
        <Row label="Year of inc." value={c.year_of_inc} />
        <Row label="Website" value={c.website} />
        <Row label="First surfaced" value={fmtDate(c.first_surfaced_at)} />
        <Row label="First funded" value={fmtDate(c.first_funded_at)} />
        <Row label="Filings" value={String(view.filingsCount)} />
        <Row label="Articles" value={String(view.articlesCount)} />
        <Row label="Tags" value={String(view.tagsCount)} />
      </dl>
      <div>
        <h4 className="font-medium" style={{ color: "var(--color-text)" }}>
          Description
        </h4>
        <p style={{ color: "var(--color-text-muted)" }}>{c.description || "—"}</p>
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string | null }) {
  return (
    <div className="flex justify-between gap-2 border-b pb-1" style={{ borderColor: "var(--color-border)" }}>
      <dt style={{ color: "var(--color-text-muted)" }}>{label}</dt>
      <dd className="text-right">{value || "—"}</dd>
    </div>
  );
}

export default async function MergeResolverPage({
  params,
}: {
  params: Promise<{ itemId: string }>;
}) {
  const { itemId } = await params;
  const item = getReviewItem(Number(itemId));
  if (!item || item.type !== "fuzzy_match" || !item.company_id || !item.other_company_id) {
    notFound();
  }

  const a = getMergeCompanyView(item.company_id);
  const b = getMergeCompanyView(item.other_company_id);
  if (!a || !b) notFound();

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="text-lg font-semibold" style={{ color: "var(--color-text)" }}>
          Resolve possible duplicate
        </h2>
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          Review item #{item.id}. Choose which record survives, or mark them as different companies.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        <Card title={`Company A (#${a.company.id})`}>
          <CompanyColumn view={a} />
        </Card>
        <Card title={`Company B (#${b.company.id})`}>
          <CompanyColumn view={b} />
        </Card>
      </div>

      <Card title="Resolve">
        <div className="flex flex-col gap-4 text-sm">
          <div className="flex flex-wrap gap-3">
            <form action={mergeCompaniesAction}>
              <input type="hidden" name="itemId" value={item.id} />
              <input type="hidden" name="survivorId" value={b.company.id} />
              <input type="hidden" name="loserId" value={a.company.id} />
              <button
                type="submit"
                className="rounded-md px-3 py-2 font-medium"
                style={{ background: "var(--color-primary)", color: "var(--color-primary-contrast)" }}
              >
                Merge A → B (B survives)
              </button>
            </form>

            <form action={mergeCompaniesAction}>
              <input type="hidden" name="itemId" value={item.id} />
              <input type="hidden" name="survivorId" value={a.company.id} />
              <input type="hidden" name="loserId" value={b.company.id} />
              <button
                type="submit"
                className="rounded-md px-3 py-2 font-medium"
                style={{ background: "var(--color-primary)", color: "var(--color-primary-contrast)" }}
              >
                Merge B → A (A survives)
              </button>
            </form>
          </div>

          <form action={notSameCompanyAction} className="flex flex-wrap items-center gap-2">
            <input type="hidden" name="itemId" value={item.id} />
            <input
              type="text"
              name="note"
              placeholder="Optional note"
              className="rounded-md border px-2 py-1"
              style={{ borderColor: "var(--color-border)" }}
            />
            <button
              type="submit"
              className="rounded-md border px-3 py-2 font-medium"
              style={{ borderColor: "var(--color-border)", color: "var(--color-text)" }}
            >
              Not the same company
            </button>
          </form>
        </div>
      </Card>

      <Link href="/review" className="text-sm" style={{ color: "var(--color-primary)" }}>
        ← Back to queue
      </Link>
    </div>
  );
}
