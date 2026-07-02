import DrawerProvider from "@/components/DrawerProvider";
import CompanyCard from "@/components/CompanyCard";
import Explorer from "@/components/Explorer";
import TrendsSection from "@/components/TrendsSection";
import { getHeroStats, getSettings, getTrends, getVisibleCompanies } from "@/lib/queries/public";
import { formatDate } from "@/lib/format";

export const dynamic = "force-dynamic";

const NEW_THIS_WEEK_WINDOW_DAYS = 14;

export default async function HomePage() {
  const settings = getSettings();
  const companies = getVisibleCompanies(settings);
  const heroStats = getHeroStats(settings);
  const trends = getTrends(settings);

  const cardsPerSection = parseInt(settings.cards_per_section, 10) || 12;
  const showTrends = settings.show_trends === "1";

  const windowStart = new Date();
  windowStart.setDate(windowStart.getDate() - NEW_THIS_WEEK_WINDOW_DAYS);

  const newThisWeek = companies
    .filter((c) => new Date(c.first_surfaced_at) >= windowStart)
    .slice(0, cardsPerSection);

  return (
    <DrawerProvider>
      <div className="mx-auto flex max-w-5xl flex-col gap-16 px-4 py-12">
        {/* Hero */}
        <section className="text-center">
          <h1 className="text-3xl font-semibold sm:text-4xl" style={{ color: "var(--color-text)" }}>
            {settings.hero_title || "New US healthtech companies, every week"}
          </h1>
          <p className="mx-auto mt-3 max-w-2xl" style={{ color: "var(--color-text-muted)" }}>
            {settings.hero_subtitle}
          </p>

          <div className="mx-auto mt-8 grid max-w-3xl grid-cols-2 gap-4 sm:grid-cols-4">
            <StatChip label="Companies tracked" value={heroStats.totalCompanies} />
            <StatChip label="Newly funded" value={heroStats.newlyFunded} />
            <StatChip label="Newly surfaced" value={heroStats.newlySurfaced} />
            <StatChip label="Newly founded" value={heroStats.newlyFounded} />
          </div>

          <p className="mt-6 text-sm" style={{ color: "var(--color-text-muted)" }}>
            Last updated: {heroStats.lastUpdated ? formatDate(heroStats.lastUpdated) : "n/a"}
          </p>
          <p className="mt-1 text-xs" style={{ color: "var(--color-text-muted)" }}>
            Every record links to its public source · Human-reviewed
          </p>
        </section>

        {/* New this week */}
        <section>
          <h2 className="mb-4 text-xl font-semibold" style={{ color: "var(--color-text)" }}>
            New this week
          </h2>
          {newThisWeek.length === 0 ? (
            <p style={{ color: "var(--color-text-muted)" }}>
              No published companies yet — records are awaiting human review.
            </p>
          ) : (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {newThisWeek.map((company) => (
                <CompanyCard
                  key={company.id}
                  company={{
                    id: company.id,
                    name_display: company.name_display,
                    state: company.state,
                    focus: company.focus,
                    industry_group: company.industry_group,
                    tags: company.tags,
                    largestRaise: company.largestRaise,
                    unreviewed: company.unreviewed,
                  }}
                />
              ))}
            </div>
          )}
        </section>

        {/* Explorer */}
        <section>
          <h2 className="mb-4 text-xl font-semibold" style={{ color: "var(--color-text)" }}>
            Explore all companies
          </h2>
          <Explorer
            companies={companies.map((company) => ({
              id: company.id,
              name_display: company.name_display,
              name_canonical: company.name_canonical,
              description: company.description,
              state: company.state,
              focus: company.focus,
              industry_group: company.industry_group,
              tags: company.tags,
              largestRaise: company.largestRaise,
              unreviewed: company.unreviewed,
              first_surfaced_at: company.first_surfaced_at,
            }))}
          />
        </section>

        {/* Trends */}
        {showTrends && (
          <section>
            <h2 className="mb-4 text-xl font-semibold" style={{ color: "var(--color-text)" }}>
              Trends
            </h2>
            <TrendsSection trends={trends} />
          </section>
        )}
      </div>
    </DrawerProvider>
  );
}

function StatChip({ label, value }: { label: string; value: number }) {
  return (
    <div
      className="rounded-lg border p-3"
      style={{ borderColor: "var(--color-border)", background: "var(--color-surface)" }}
    >
      <div className="text-2xl font-semibold" style={{ color: "var(--color-primary)" }}>
        {value}
      </div>
      <div className="text-xs" style={{ color: "var(--color-text-muted)" }}>
        {label}
      </div>
    </div>
  );
}
