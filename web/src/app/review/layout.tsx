import Link from "next/link";
import { requireRole } from "@/lib/auth";

export default async function ReviewLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  await requireRole("reviewer");

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-xl font-semibold" style={{ color: "var(--color-text)" }}>
          Reviewer tool
        </h1>
        <nav className="flex gap-4 text-sm font-medium">
          <Link href="/review" style={{ color: "var(--color-primary)" }}>
            Queue
          </Link>
          <Link href="/review/qa" style={{ color: "var(--color-primary)" }}>
            QA runs
          </Link>
        </nav>
      </div>
      {children}
    </div>
  );
}
