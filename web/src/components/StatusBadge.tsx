import type { CompanyStatus } from "@/lib/types";

const STYLES: Record<CompanyStatus, { bg: string; fg: string; label: string }> = {
  pending_review: { bg: "#fef3c7", fg: "#92400e", label: "Pending review" },
  published: { bg: "#dcfce7", fg: "#166534", label: "Published" },
  invalidated: { bg: "#fee2e2", fg: "#991b1b", label: "Invalidated" },
  archived: { bg: "#e5e7eb", fg: "#374151", label: "Archived" },
};

export default function StatusBadge({ status }: { status: CompanyStatus }) {
  const s = STYLES[status] ?? STYLES.pending_review;
  return (
    <span
      className="inline-block rounded-full px-2 py-0.5 text-xs font-medium"
      style={{ background: s.bg, color: s.fg }}
    >
      {s.label}
    </span>
  );
}
