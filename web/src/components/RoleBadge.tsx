import type { Role } from "@/lib/types";

const STYLES: Record<Role, { bg: string; fg: string; label: string }> = {
  viewer: { bg: "#e5e7eb", fg: "#374151", label: "Viewer" },
  reviewer: { bg: "#cffafe", fg: "#155e75", label: "Reviewer" },
  admin: { bg: "#ccfbf1", fg: "#0f766e", label: "Admin" },
};

export default function RoleBadge({ role }: { role: Role }) {
  const s = STYLES[role] ?? STYLES.viewer;
  return (
    <span
      className="inline-block rounded-full px-2 py-0.5 text-xs font-medium"
      style={{ background: s.bg, color: s.fg }}
    >
      {s.label}
    </span>
  );
}
