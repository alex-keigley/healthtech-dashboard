"use client";

import { useEffect, useState } from "react";
import type { Article, Company, Filing, TechTag } from "@/lib/types";
import { formatDate, formatMoney } from "@/lib/format";

interface DrawerDetail {
  company: Company & { unreviewed: boolean };
  filings: Filing[];
  articles: Article[];
  tags: TechTag[];
}

export default function CompanyDrawer({
  companyId,
  onClose,
  onOpen,
}: {
  companyId: number | null;
  onClose: () => void;
  onOpen: (id: number) => void;
}) {
  const [detail, setDetail] = useState<DrawerDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);

  const open = companyId !== null;

  // Auto-open from ?company=<id> on first mount.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const fromUrl = params.get("company");
    if (fromUrl) {
      const parsed = parseInt(fromUrl, 10);
      if (!Number.isNaN(parsed)) {
        onOpen(parsed);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Fetch detail + sync deep-link URL whenever the open company changes.
  useEffect(() => {
    if (companyId === null) {
      window.history.replaceState(null, "", "/");
      return;
    }

    window.history.replaceState(null, "", `?company=${companyId}`);
    setLoading(true);
    setError(false);
    setDetail(null);

    fetch(`/api/companies/${companyId}`)
      .then((res) => {
        if (!res.ok) throw new Error("not found");
        return res.json();
      })
      .then((data: DrawerDetail) => setDetail(data))
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [companyId]);

  // Esc key closes.
  useEffect(() => {
    if (!open) return;
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [open, onClose]);

  return (
    <>
      {/* Backdrop */}
      <div
        className={`fixed inset-0 z-40 bg-black/30 transition-opacity ${
          open ? "opacity-100" : "pointer-events-none opacity-0"
        }`}
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Drawer */}
      <div
        className={`fixed inset-x-0 bottom-0 z-50 max-h-[80vh] overflow-y-auto rounded-t-lg transition-transform duration-300 md:inset-y-0 md:right-0 md:left-auto md:h-full md:max-h-none md:w-[440px] md:rounded-t-none md:rounded-l-lg ${
          open ? "translate-y-0 md:translate-x-0" : "translate-y-full md:translate-y-0 md:translate-x-full"
        }`}
        style={{ background: "var(--color-surface)", borderLeft: "1px solid var(--color-border)" }}
        role="dialog"
        aria-modal="true"
      >
        <div className="flex items-center justify-between border-b px-5 py-4" style={{ borderColor: "var(--color-border)" }}>
          <h2 className="text-lg font-semibold" style={{ color: "var(--color-text)" }}>
            Company details
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md px-2 py-1 text-sm"
            style={{ color: "var(--color-text-muted)" }}
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        <div className="px-5 py-4">
          {loading && (
            <p style={{ color: "var(--color-text-muted)" }}>Loading…</p>
          )}
          {error && !loading && (
            <p style={{ color: "var(--color-danger)" }}>Could not load company details.</p>
          )}
          {detail && !loading && !error && (
            <div className="flex flex-col gap-5">
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-xl font-semibold" style={{ color: "var(--color-text)" }}>
                    {detail.company.name_display}
                  </h3>
                  {detail.company.unreviewed && (
                    <span
                      className="rounded-full px-2 py-0.5 text-xs font-medium"
                      style={{ background: "#fef3c7", color: "#92400e" }}
                    >
                      Unreviewed
                    </span>
                  )}
                </div>

                {detail.company.description && (
                  <p className="mt-2 text-sm" style={{ color: "var(--color-text-muted)" }}>
                    {detail.company.description}
                  </p>
                )}
                {detail.company.description_url && (
                  <a
                    href={detail.company.description_url}
                    target="_blank"
                    rel="noreferrer"
                    className="mt-1 inline-block text-xs"
                  >
                    Source: {detail.company.description_source || "source"}
                  </a>
                )}
              </div>

              <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
                <DetailRow label="Focus" value={detail.company.focus} />
                <DetailRow label="State" value={detail.company.state} />
                <DetailRow label="Year of incorporation" value={detail.company.year_of_inc} />
                <DetailRow label="Entity type" value={detail.company.entity_type} />
                <DetailRow label="Industry group" value={detail.company.industry_group} />
                {detail.company.website && (
                  <div>
                    <dt className="text-xs uppercase tracking-wide" style={{ color: "var(--color-text-muted)" }}>
                      Website
                    </dt>
                    <dd>
                      <a href={detail.company.website} target="_blank" rel="noreferrer">
                        {detail.company.website}
                      </a>
                    </dd>
                  </div>
                )}
              </dl>

              {detail.tags.length > 0 && (
                <section>
                  <h4 className="mb-2 text-sm font-semibold" style={{ color: "var(--color-text)" }}>
                    Technology tags
                  </h4>
                  <ul className="flex flex-wrap gap-1.5">
                    {detail.tags.map((tag) => (
                      <li
                        key={tag.category}
                        className="rounded-full px-2 py-0.5 text-xs"
                        style={{ background: "var(--color-bg)", color: "var(--color-text-muted)", border: "1px solid var(--color-border)" }}
                      >
                        {tag.category} ({Math.round(tag.confidence * 100)}%)
                      </li>
                    ))}
                  </ul>
                </section>
              )}

              {detail.filings.length > 0 && (
                <section>
                  <h4 className="mb-2 text-sm font-semibold" style={{ color: "var(--color-text)" }}>
                    Filings
                  </h4>
                  <ul className="flex flex-col gap-2">
                    {detail.filings.map((filing) => (
                      <li
                        key={filing.accession}
                        className="rounded-md border p-2 text-sm"
                        style={{ borderColor: "var(--color-border)" }}
                      >
                        <div className="flex items-center justify-between">
                          <span>{formatDate(filing.filing_date)}</span>
                          <span className="font-medium">{formatMoney(filing.total_offering_amount)}</span>
                        </div>
                        {filing.filing_url && (
                          <a href={filing.filing_url} target="_blank" rel="noreferrer" className="text-xs">
                            View on {filing.source || "SEC EDGAR"}
                          </a>
                        )}
                      </li>
                    ))}
                  </ul>
                </section>
              )}

              {detail.articles.length > 0 && (
                <section>
                  <h4 className="mb-2 text-sm font-semibold" style={{ color: "var(--color-text)" }}>
                    Press mentions
                  </h4>
                  <ul className="flex flex-col gap-2">
                    {detail.articles.map((article) => (
                      <li key={article.id} className="text-sm">
                        <a href={article.url} target="_blank" rel="noreferrer">
                          {article.title}
                        </a>
                        <div className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                          {article.source} · {formatDate(article.published_at)}
                        </div>
                      </li>
                    ))}
                  </ul>
                </section>
              )}
            </div>
          )}
        </div>
      </div>
    </>
  );
}

function DetailRow({ label, value }: { label: string; value: string | null }) {
  if (!value) return null;
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide" style={{ color: "var(--color-text-muted)" }}>
        {label}
      </dt>
      <dd style={{ color: "var(--color-text)" }}>{value}</dd>
    </div>
  );
}
