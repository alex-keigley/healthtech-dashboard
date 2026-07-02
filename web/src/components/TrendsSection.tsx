import WeeklyFilingsChart from "@/components/charts/WeeklyFilingsChart";
import TopCategoriesChart from "@/components/charts/TopCategoriesChart";
import TopStatesChart from "@/components/charts/TopStatesChart";
import type { TrendsData } from "@/lib/queries/public";

export default function TrendsSection({ trends }: { trends: TrendsData }) {
  const hasAnyFilings = trends.filingsPerWeek.some((w) => w.count > 0);
  const isEmpty =
    !hasAnyFilings && trends.topCategories.length === 0 && trends.companiesByState.length === 0;

  if (isEmpty) {
    return (
      <p className="text-center" style={{ color: "var(--color-text-muted)" }}>
        No published companies yet — records are awaiting human review.
      </p>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
      <div className="rounded-lg border p-4" style={{ borderColor: "var(--color-border)", background: "var(--color-surface)" }}>
        <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide" style={{ color: "var(--color-text-muted)" }}>
          Weekly filing volume
        </h3>
        <WeeklyFilingsChart data={trends.filingsPerWeek} />
      </div>

      <div className="rounded-lg border p-4" style={{ borderColor: "var(--color-border)", background: "var(--color-surface)" }}>
        <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide" style={{ color: "var(--color-text-muted)" }}>
          Top categories
        </h3>
        <TopCategoriesChart data={trends.topCategories} />
      </div>

      <div className="rounded-lg border p-4 lg:col-span-2" style={{ borderColor: "var(--color-border)", background: "var(--color-surface)" }}>
        <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide" style={{ color: "var(--color-text-muted)" }}>
          Top states
        </h3>
        <TopStatesChart data={trends.companiesByState} />
      </div>
    </div>
  );
}
