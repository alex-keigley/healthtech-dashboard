import Card from "@/components/Card";
import LevelBadge from "@/components/LevelBadge";
import { listPipelineRuns, parseQaFindings, prettyStats } from "@/lib/queries/review";
import { acknowledgeRunAction } from "@/app/review/actions";

export const dynamic = "force-dynamic";

function fmtDateTime(iso: string | null): string {
  if (!iso) return "—";
  return iso.replace("T", " ").slice(0, 19);
}

export default async function QaRunsPage() {
  const runs = listPipelineRuns();

  return (
    <div className="flex flex-col gap-4">
      <h2 className="text-lg font-semibold" style={{ color: "var(--color-text)" }}>
        Pipeline runs &amp; QA findings
      </h2>

      {runs.length === 0 && (
        <Card>
          <p style={{ color: "var(--color-text-muted)" }}>No pipeline runs recorded yet.</p>
        </Card>
      )}

      {runs.map((run) => {
        const findings = parseQaFindings(run);
        return (
          <Card
            key={run.id}
            title={`Run #${run.id} · ${run.status}`}
            actions={
              findings.length > 0 && !run.qa_acked_at ? (
                <form action={acknowledgeRunAction}>
                  <input type="hidden" name="runId" value={run.id} />
                  <button
                    type="submit"
                    className="rounded-md px-3 py-1 text-xs font-medium"
                    style={{ background: "var(--color-primary)", color: "var(--color-primary-contrast)" }}
                  >
                    Acknowledge
                  </button>
                </form>
              ) : run.qa_acked_at ? (
                <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                  Acknowledged {fmtDateTime(run.qa_acked_at)}
                </span>
              ) : null
            }
          >
            <div className="flex flex-col gap-2 text-sm">
              <div style={{ color: "var(--color-text-muted)" }}>
                Started {fmtDateTime(run.started_at)} · Finished {fmtDateTime(run.finished_at)}
                {run.window_start && (
                  <> · Window {run.window_start.slice(0, 10)} → {run.window_end?.slice(0, 10) ?? "?"}</>
                )}
              </div>

              {run.stats && (
                <div>
                  <span className="font-medium">Stats: </span>
                  <code
                    className="rounded-md px-2 py-0.5 text-xs"
                    style={{ background: "var(--color-bg)" }}
                  >
                    {prettyStats(run)}
                  </code>
                </div>
              )}

              {findings.length > 0 ? (
                <ul className="flex flex-col gap-1">
                  {findings.map((f, i) => (
                    <li key={i} className="flex items-center gap-2 border-b py-1" style={{ borderColor: "var(--color-border)" }}>
                      <LevelBadge level={f.level} />
                      <span className="font-medium">{f.gate}</span>
                      <span style={{ color: "var(--color-text-muted)" }}>{f.message}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p style={{ color: "var(--color-text-muted)" }}>No QA findings.</p>
              )}
            </div>
          </Card>
        );
      })}
    </div>
  );
}
