"use client";

import { useDrawer } from "@/components/DrawerProvider";
import { formatMoney } from "@/lib/format";

export interface CompanyCardData {
  id: number;
  name_display: string;
  state: string | null;
  focus: string | null;
  industry_group: string | null;
  tags: string[];
  largestRaise: number | null;
  unreviewed: boolean;
}

export default function CompanyCard({ company }: { company: CompanyCardData }) {
  const { openDrawer } = useDrawer();
  const focusLabel = company.focus || company.industry_group;

  return (
    <button
      type="button"
      onClick={() => openDrawer(company.id)}
      className="flex h-full w-full flex-col items-start gap-2 rounded-lg border p-4 text-left transition hover:shadow-sm"
      style={{ borderColor: "var(--color-border)", background: "var(--color-surface)" }}
    >
      <div className="flex w-full items-start justify-between gap-2">
        <h3 className="font-semibold" style={{ color: "var(--color-text)" }}>
          {company.name_display}
        </h3>
        {company.unreviewed && (
          <span
            className="shrink-0 rounded-full px-2 py-0.5 text-xs font-medium"
            style={{ background: "#fef3c7", color: "#92400e" }}
          >
            Unreviewed
          </span>
        )}
      </div>

      <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
        {[company.state, focusLabel].filter(Boolean).join(" · ") || "—"}
      </p>

      {company.tags.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {company.tags.slice(0, 3).map((tag) => (
            <span
              key={tag}
              className="rounded-full px-2 py-0.5 text-xs"
              style={{ background: "var(--color-bg)", color: "var(--color-text-muted)", border: "1px solid var(--color-border)" }}
            >
              {tag}
            </span>
          ))}
        </div>
      )}

      {company.largestRaise ? (
        <p className="mt-auto pt-1 text-sm font-medium" style={{ color: "var(--color-primary)" }}>
          {formatMoney(company.largestRaise)} raised
        </p>
      ) : null}
    </button>
  );
}
