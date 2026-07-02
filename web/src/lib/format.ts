// Shared display-formatting helpers for the public dashboard.

export function formatMoney(amount: number | null): string {
  if (amount === null || amount === undefined || amount === 0) return "—";

  const abs = Math.abs(amount);
  const sign = amount < 0 ? "-" : "";

  if (abs >= 1_000_000) {
    const millions = Math.round((abs / 1_000_000) * 10) / 10;
    return `${sign}$${millions.toFixed(1)}M`;
  }
  if (abs >= 1_000) {
    const thousands = Math.round(abs / 1_000);
    return `${sign}$${thousands}K`;
  }
  return `${sign}$${Math.round(abs)}`;
}

const DATE_FORMATTER = new Intl.DateTimeFormat("en-US", {
  month: "short",
  day: "numeric",
  year: "numeric",
  timeZone: "UTC",
});

export function formatDate(iso: string | null): string {
  if (!iso) return "—";
  // Date-only strings ("2026-06-28") parse as UTC midnight; full ISO
  // timestamps parse as-is. Format in UTC either way so date-only
  // strings don't shift a day depending on local timezone.
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return DATE_FORMATTER.format(d);
}
