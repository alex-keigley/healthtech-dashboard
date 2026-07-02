import Card from "@/components/Card";
import LevelBadge from "@/components/LevelBadge";
import { listPipelineRunsForAdmin } from "@/lib/queries/admin";
import { parseQaFindings, prettyStats } from "@/lib/queries/review";

export const dynamic = "force-dynamic";

function fmtDateTime(iso: string | null): string {
  if (!iso) return "—";
  return iso.replace("T", " ").slice(0, 19);
}

export default async function AdminPipelinePage() {
  const runs = listPipelineRunsForAdmin();

  return (
    <div className="flex flex-col gap-6">
      <Card title="How to trigger a manual run">
        <div className="flex flex-col gap-3 text-sm">
          <div>
            <p className="font-medium" style={{ color: "var(--color-text)" }}>
              Dev (Windows, native)
            </p>
            <code
              className="mt-1 block rounded-md px-3 py-2"
              style={{ background: "var(--color-bg)" }}
            >
              cd pipeline &amp;&amp; python -m pipeline.run --days 7
            </code>
          </div>
          <div>
            <p className="font-medium" style={{ color: "var(--color-text)" }}>
              Prod (Docker Compose)
            </p>
            <code
              className="mt-1 block rounded-md px-3 py-2"
              style={{ background: "var(--color-bg)" }}
            >
              docker compose run --rm pipeline python -m pipeline.run --days 7
            </code>
          </div>
          <p style={{ color: "var(--color-text-muted)" }}>
            The scheduler container also runs this automatically every Sunday at 06:00 UTC.
            New records land in the review queue as <code>pending_review</code> — nothing
            becomes public until a reviewer validates it.
          </p>
        </div>
      </Card>

      <Card title="Pipeline runs">
        <div className="flex flex-col gap-4 text-sm">
          {runs.length === 0 && (
            <p style={{ color: "var(--color-text-muted)" }}>No pipeline runs recorded yet.</p>
          )}
          {runs.map((run) => {
            const findings = parseQaFindings(run);
            return (
              <div key={run.id} className="border-b pb-4" style={{ borderColor: "var(--color-border)" }}>
                <div className="flex items-center justify-between">
                  <span className="font-medium">
                    Run #{run.id} · {run.status}
                  </span>
                  <span style={{ color: "var(--color-text-muted)" }}>
                    {fmtDateTime(run.started_at)} → {fmtDateTime(run.finished_at)}
                  </span>
                </div>
                {run.stats && (
                  <code
                    className="mt-2 block rounded-md px-2 py-1 text-xs"
                    style={{ background: "var(--color-bg)" }}
                  >
                    {prettyStats(run)}
                  </code>
                )}
                {findings.length > 0 && (
                  <ul className="mt-2 flex flex-col gap-1">
                    {findings.map((f, i) => (
                      <li key={i} className="flex items-center gap-2">
                        <LevelBadge level={f.level} />
                        <span className="font-medium">{f.gate}</span>
                        <span style={{ color: "var(--color-text-muted)" }}>{f.message}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            );
          })}
        </div>
      </Card>
    </div>
  );
}
