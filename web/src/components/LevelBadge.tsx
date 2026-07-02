const STYLES: Record<string, { bg: string; fg: string }> = {
  info: { bg: "#dbeafe", fg: "#1e40af" },
  warning: { bg: "#fef3c7", fg: "#92400e" },
  error: { bg: "#fee2e2", fg: "#991b1b" },
  critical: { bg: "#fee2e2", fg: "#7f1d1d" },
};

export default function LevelBadge({ level }: { level: string }) {
  const s = STYLES[level?.toLowerCase()] ?? { bg: "#e5e7eb", fg: "#374151" };
  return (
    <span
      className="inline-block rounded-full px-2 py-0.5 text-xs font-medium uppercase tracking-wide"
      style={{ background: s.bg, color: s.fg }}
    >
      {level}
    </span>
  );
}
