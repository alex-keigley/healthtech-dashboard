import Link from "next/link";
import Card from "@/components/Card";
import StatusBadge from "@/components/StatusBadge";
import {
  countsByState,
  countsByType,
  listQueue,
} from "@/lib/queries/review";
import { claimItemAction, dismissItemAction } from "@/app/review/actions";
import type { CompanyStatus, ReviewItemState, ReviewItemType } from "@/lib/types";

export const dynamic = "force-dynamic";

const TYPE_LABELS: Record<ReviewItemType, string> = {
  new_record: "New record",
  untagged: "Untagged",
  low_confidence: "Low confidence",
  fuzzy_match: "Fuzzy match",
};

const STATE_LABELS: Record<ReviewItemState, string> = {
  open: "Open",
  resolved: "Resolved",
  dismissed: "Dismissed",
};

function humanAge(iso: string): string {
  const ms = Date.now() - new Date(iso).getTime();
  const days = Math.floor(ms / (1000 * 60 * 60 * 24));
  if (days <= 0) return "today";
  if (days === 1) return "1 day ago";
  return `${days} days ago`;
}

export default async function ReviewQueuePage({
  searchParams,
}: {
  searchParams: Promise<{ type?: string; state?: string; search?: string }>;
}) {
  const params = await searchParams;
  const typeCounts = countsByType();
  const stateCounts = countsByState();
  const rows = listQueue({
    type: params.type,
    state: params.state,
    search: params.search,
  });

  const typeCountMap = Object.fromEntries(typeCounts.map((t) => [t.type, t.n]));
  const stateCountMap = Object.fromEntries(stateCounts.map((s) => [s.state, s.n]));

  return (
    <div className="flex flex-col gap-6">
      <Card title="Open items by type">
        <div className="flex flex-wrap gap-2">
          {(Object.keys(TYPE_LABELS) as ReviewItemType[]).map((t) => (
            <Link
              key={t}
              href={`/review?type=${t}`}
              className="rounded-full border px-3 py-1 text-sm"
              style={{
                borderColor: "var(--color-border)",
                background: params.type === t ? "var(--color-primary)" : "var(--color-surface)",
                color: params.type === t ? "var(--color-primary-contrast)" : "var(--color-text)",
              }}
            >
              {TYPE_LABELS[t]} ({typeCountMap[t] ?? 0})
            </Link>
          ))}
        </div>
      </Card>

      <Card title="Items by state">
        <div className="flex flex-wrap gap-2">
          {(Object.keys(STATE_LABELS) as ReviewItemState[]).map((s) => (
            <Link
              key={s}
              href={`/review?state=${s}`}
              className="rounded-full border px-3 py-1 text-sm"
              style={{
                borderColor: "var(--color-border)",
                background: params.state === s ? "var(--color-primary)" : "var(--color-surface)",
                color: params.state === s ? "var(--color-primary-contrast)" : "var(--color-text)",
              }}
            >
              {STATE_LABELS[s]} ({stateCountMap[s] ?? 0})
            </Link>
          ))}
          <Link
            href="/review"
            className="rounded-full border px-3 py-1 text-sm"
            style={{ borderColor: "var(--color-border)", color: "var(--color-text-muted)" }}
          >
            Clear filters
          </Link>
        </div>
      </Card>

      <Card
        title="Queue"
        actions={
          <form method="get" className="flex gap-2">
            {params.type && <input type="hidden" name="type" value={params.type} />}
            {params.state && <input type="hidden" name="state" value={params.state} />}
            <input
              type="text"
              name="search"
              placeholder="Search company name"
              defaultValue={params.search || ""}
              className="rounded-md border px-2 py-1 text-sm"
              style={{ borderColor: "var(--color-border)" }}
            />
            <button
              type="submit"
              className="rounded-md px-3 py-1 text-sm font-medium"
              style={{ background: "var(--color-primary)", color: "var(--color-primary-contrast)" }}
            >
              Search
            </button>
          </form>
        }
      >
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr style={{ color: "var(--color-text-muted)" }}>
                <th className="py-2 pr-3">Type</th>
                <th className="py-2 pr-3">Company</th>
                <th className="py-2 pr-3">State</th>
                <th className="py-2 pr-3">Focus</th>
                <th className="py-2 pr-3">Type</th>
                <th className="py-2 pr-3">Status</th>
                <th className="py-2 pr-3">Assignee</th>
                <th className="py-2 pr-3">Age</th>
                <th className="py-2 pr-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                const href =
                  row.type === "fuzzy_match"
                    ? `/review/merge/${row.id}`
                    : `/review/company/${row.company_id}`;
                return (
                  <tr key={row.id} className="border-t" style={{ borderColor: "var(--color-border)" }}>
                    <td className="py-2 pr-3">{TYPE_LABELS[row.type]}</td>
                    <td className="py-2 pr-3">
                      <Link href={href} className="font-medium" style={{ color: "var(--color-primary)" }}>
                        {row.company_name || `#${row.company_id ?? "?"}`}
                      </Link>
                    </td>
                    <td className="py-2 pr-3">{row.company_state || "—"}</td>
                    <td className="py-2 pr-3">{row.company_focus || "—"}</td>
                    <td className="py-2 pr-3">{row.company_type || "—"}</td>
                    <td className="py-2 pr-3">
                      {row.company_status ? (
                        <StatusBadge status={row.company_status as CompanyStatus} />
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="py-2 pr-3">{row.assignee_email || "—"}</td>
                    <td className="py-2 pr-3">{humanAge(row.created_at)}</td>
                    <td className="py-2 pr-3">
                      <div className="flex flex-wrap items-center gap-2">
                        {row.state === "open" && (
                          <form action={claimItemAction}>
                            <input type="hidden" name="itemId" value={row.id} />
                            <button
                              type="submit"
                              className="rounded-md border px-2 py-1 text-xs font-medium"
                              style={{ borderColor: "var(--color-border)" }}
                            >
                              Claim
                            </button>
                          </form>
                        )}
                        {row.state === "open" && (
                          <form action={dismissItemAction} className="flex items-center gap-1">
                            <input type="hidden" name="itemId" value={row.id} />
                            <input
                              type="text"
                              name="note"
                              placeholder="Reason"
                              required
                              className="w-28 rounded-md border px-2 py-1 text-xs"
                              style={{ borderColor: "var(--color-border)" }}
                            />
                            <button
                              type="submit"
                              className="rounded-md border px-2 py-1 text-xs font-medium"
                              style={{ borderColor: "var(--color-border)", color: "var(--color-danger)" }}
                            >
                              Dismiss
                            </button>
                          </form>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
              {rows.length === 0 && (
                <tr>
                  <td colSpan={9} className="py-6 text-center" style={{ color: "var(--color-text-muted)" }}>
                    No items match these filters.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
