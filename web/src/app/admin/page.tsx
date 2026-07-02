import Link from "next/link";
import Card from "@/components/Card";
import {
  countCompaniesByStatus,
  countOpenReviewItems,
  countUsersByRole,
} from "@/lib/queries/admin";

export const dynamic = "force-dynamic";

export default async function AdminOverviewPage() {
  const usersByRole = countUsersByRole();
  const companiesByStatus = countCompaniesByStatus();
  const openReviewItems = countOpenReviewItems();

  return (
    <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
      <Card title="Users">
        <ul className="flex flex-col gap-1 text-sm">
          {usersByRole.map((r) => (
            <li key={r.role} className="flex justify-between">
              <span className="capitalize">{r.role}</span>
              <span className="font-medium">{r.n}</span>
            </li>
          ))}
        </ul>
        <Link href="/admin/users" className="mt-3 inline-block text-sm font-medium" style={{ color: "var(--color-primary)" }}>
          Manage users →
        </Link>
      </Card>

      <Card title="Companies">
        <ul className="flex flex-col gap-1 text-sm">
          {companiesByStatus.map((s) => (
            <li key={s.status} className="flex justify-between">
              <span className="capitalize">{s.status.replace("_", " ")}</span>
              <span className="font-medium">{s.n}</span>
            </li>
          ))}
        </ul>
      </Card>

      <Card title="Review queue">
        <p className="text-2xl font-semibold" style={{ color: "var(--color-text)" }}>
          {openReviewItems}
        </p>
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          open review items
        </p>
        <Link href="/review" className="mt-3 inline-block text-sm font-medium" style={{ color: "var(--color-primary)" }}>
          Go to reviewer tool →
        </Link>
      </Card>

      <Card title="Settings" className="md:col-span-1">
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          Hero copy, publish policy, featured categories.
        </p>
        <Link href="/admin/settings" className="mt-3 inline-block text-sm font-medium" style={{ color: "var(--color-primary)" }}>
          Edit settings →
        </Link>
      </Card>

      <Card title="Pipeline" className="md:col-span-1">
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          Run history and manual trigger instructions.
        </p>
        <Link href="/admin/pipeline" className="mt-3 inline-block text-sm font-medium" style={{ color: "var(--color-primary)" }}>
          View pipeline →
        </Link>
      </Card>
    </div>
  );
}
