import Card from "@/components/Card";
import RoleBadge from "@/components/RoleBadge";
import { getSessionUser } from "@/lib/auth";
import { listUsers } from "@/lib/queries/admin";
import {
  createUserAction,
  resetPasswordAction,
  toggleDisabledAction,
  updateRoleAction,
} from "@/app/admin/actions";
import type { Role } from "@/lib/types";

export const dynamic = "force-dynamic";

const ROLES: Role[] = ["viewer", "reviewer", "admin"];

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  return iso.slice(0, 10);
}

export default async function AdminUsersPage() {
  const me = await getSessionUser();
  const users = listUsers();

  return (
    <div className="flex flex-col gap-6">
      <Card title="Create user">
        <form action={createUserAction} className="flex flex-wrap items-end gap-3 text-sm">
          <label className="flex flex-col gap-1">
            Email
            <input
              type="email"
              name="email"
              required
              className="rounded-md border px-2 py-1"
              style={{ borderColor: "var(--color-border)" }}
            />
          </label>
          <label className="flex flex-col gap-1">
            Name
            <input
              type="text"
              name="name"
              className="rounded-md border px-2 py-1"
              style={{ borderColor: "var(--color-border)" }}
            />
          </label>
          <label className="flex flex-col gap-1">
            Role
            <select
              name="role"
              defaultValue="viewer"
              className="rounded-md border px-2 py-1"
              style={{ borderColor: "var(--color-border)" }}
            >
              {ROLES.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1">
            Initial password (optional)
            <input
              type="text"
              name="password"
              placeholder="Leave blank for OTP login"
              className="rounded-md border px-2 py-1"
              style={{ borderColor: "var(--color-border)" }}
            />
          </label>
          <button
            type="submit"
            className="rounded-md px-3 py-2 font-medium"
            style={{ background: "var(--color-primary)", color: "var(--color-primary-contrast)" }}
          >
            Create
          </button>
        </form>
      </Card>

      <Card title="Users">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr style={{ color: "var(--color-text-muted)" }}>
                <th className="py-2 pr-3">Email</th>
                <th className="py-2 pr-3">Name</th>
                <th className="py-2 pr-3">Role</th>
                <th className="py-2 pr-3">Disabled</th>
                <th className="py-2 pr-3">Last login</th>
                <th className="py-2 pr-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => {
                const isSelf = me?.id === u.id;
                return (
                  <tr key={u.id} className="border-t align-top" style={{ borderColor: "var(--color-border)" }}>
                    <td className="py-2 pr-3">{u.email}</td>
                    <td className="py-2 pr-3">{u.name || "—"}</td>
                    <td className="py-2 pr-3">
                      <div className="flex items-center gap-2">
                        <RoleBadge role={u.role} />
                        <form action={updateRoleAction} className="flex items-center gap-1">
                          <input type="hidden" name="userId" value={u.id} />
                          <select
                            name="role"
                            defaultValue={u.role}
                            disabled={isSelf}
                            className="rounded-md border px-1 py-0.5 text-xs"
                            style={{ borderColor: "var(--color-border)" }}
                          >
                            {ROLES.map((r) => (
                              <option key={r} value={r}>
                                {r}
                              </option>
                            ))}
                          </select>
                          {!isSelf && (
                            <button
                              type="submit"
                              className="rounded-md border px-2 py-0.5 text-xs font-medium"
                              style={{ borderColor: "var(--color-border)" }}
                            >
                              Set
                            </button>
                          )}
                        </form>
                      </div>
                    </td>
                    <td className="py-2 pr-3">
                      <form action={toggleDisabledAction}>
                        <input type="hidden" name="userId" value={u.id} />
                        <input type="hidden" name="disable" value={u.disabled ? "0" : "1"} />
                        <button
                          type="submit"
                          disabled={isSelf && !u.disabled}
                          className="rounded-md border px-2 py-1 text-xs font-medium"
                          style={{
                            borderColor: "var(--color-border)",
                            color: u.disabled ? "var(--color-success)" : "var(--color-danger)",
                            opacity: isSelf && !u.disabled ? 0.5 : 1,
                          }}
                        >
                          {u.disabled ? "Enable" : "Disable"}
                        </button>
                      </form>
                    </td>
                    <td className="py-2 pr-3">{fmtDate(u.last_login_at)}</td>
                    <td className="py-2 pr-3">
                      <form action={resetPasswordAction} className="flex items-center gap-1">
                        <input type="hidden" name="userId" value={u.id} />
                        <input
                          type="text"
                          name="password"
                          placeholder="New password"
                          required
                          className="w-32 rounded-md border px-2 py-1 text-xs"
                          style={{ borderColor: "var(--color-border)" }}
                        />
                        <button
                          type="submit"
                          className="rounded-md border px-2 py-1 text-xs font-medium"
                          style={{ borderColor: "var(--color-border)" }}
                        >
                          Reset password
                        </button>
                      </form>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
