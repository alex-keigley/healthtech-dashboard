import Link from "next/link";
import { requireRole } from "@/lib/auth";

export default async function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  await requireRole("admin");

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-xl font-semibold" style={{ color: "var(--color-text)" }}>
          Admin panel
        </h1>
        <nav className="flex gap-4 text-sm font-medium">
          <Link href="/admin" style={{ color: "var(--color-primary)" }}>
            Overview
          </Link>
          <Link href="/admin/users" style={{ color: "var(--color-primary)" }}>
            Users
          </Link>
          <Link href="/admin/settings" style={{ color: "var(--color-primary)" }}>
            Settings
          </Link>
          <Link href="/admin/pipeline" style={{ color: "var(--color-primary)" }}>
            Pipeline
          </Link>
        </nav>
      </div>
      {children}
    </div>
  );
}
