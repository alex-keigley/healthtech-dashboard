import LoginForm from "./LoginForm";

export const dynamic = "force-dynamic";

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string }>;
}) {
  const { next } = await searchParams;

  return (
    <div className="mx-auto flex max-w-sm flex-col gap-6 px-4 py-16">
      <div className="text-center">
        <h1 className="text-2xl font-semibold" style={{ color: "var(--color-text)" }}>
          Sign in
        </h1>
        <p className="mt-1 text-sm" style={{ color: "var(--color-text-muted)" }}>
          Reviewer and admin access is invite-only.
        </p>
      </div>
      <LoginForm next={next || "/"} />
    </div>
  );
}
