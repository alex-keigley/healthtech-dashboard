import Link from "next/link";
import { getSessionUser } from "@/lib/auth";
import { signOutAction } from "@/app/login/actions";

export default async function Header() {
  const user = await getSessionUser();

  return (
    <header
      className="border-b"
      style={{ borderColor: "var(--color-border)", background: "var(--color-surface)" }}
    >
      <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3">
        <Link href="/" className="font-semibold" style={{ color: "var(--color-text)" }}>
          Healthtech Dashboard
        </Link>
        <nav className="flex items-center gap-4 text-sm">
          <Link href="/methodology" style={{ color: "var(--color-text-muted)" }}>
            Methodology
          </Link>
          {user && (user.role === "reviewer" || user.role === "admin") && (
            <Link href="/review" style={{ color: "var(--color-text-muted)" }}>
              Review
            </Link>
          )}
          {user && user.role === "admin" && (
            <Link href="/admin" style={{ color: "var(--color-text-muted)" }}>
              Admin
            </Link>
          )}
          {user ? (
            <form action={signOutAction}>
              <button
                type="submit"
                className="text-sm font-medium"
                style={{ color: "var(--color-primary)" }}
              >
                Sign out
              </button>
            </form>
          ) : (
            <Link
              href="/login"
              className="text-sm font-medium"
              style={{ color: "var(--color-primary)" }}
            >
              Sign in
            </Link>
          )}
        </nav>
      </div>
    </header>
  );
}
