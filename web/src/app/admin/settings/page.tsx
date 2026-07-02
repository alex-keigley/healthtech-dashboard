import Card from "@/components/Card";
import { TAXONOMY } from "@/lib/taxonomy";
import { getAllSettings } from "@/lib/queries/admin";
import { saveSettingsAction } from "@/app/admin/actions";

export const dynamic = "force-dynamic";

export default async function AdminSettingsPage() {
  const settings = getAllSettings();
  const featuredCategories: string[] = (() => {
    try {
      const parsed = JSON.parse(settings.featured_categories || "[]");
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  })();

  return (
    <Card title="Presentation settings">
      <form action={saveSettingsAction} className="flex flex-col gap-6 text-sm">
        <label className="flex flex-col gap-1">
          <span className="font-medium">Hero title</span>
          <input
            type="text"
            name="hero_title"
            defaultValue={settings.hero_title || ""}
            className="rounded-md border px-2 py-1"
            style={{ borderColor: "var(--color-border)" }}
          />
        </label>

        <label className="flex flex-col gap-1">
          <span className="font-medium">Hero subtitle</span>
          <textarea
            name="hero_subtitle"
            defaultValue={settings.hero_subtitle || ""}
            rows={3}
            className="rounded-md border px-2 py-1"
            style={{ borderColor: "var(--color-border)" }}
          />
        </label>

        <fieldset className="flex flex-col gap-2">
          <legend className="font-medium">Publish policy</legend>
          <label className="flex items-start gap-2">
            <input
              type="radio"
              name="publish_policy"
              value="fail_closed"
              defaultChecked={settings.publish_policy !== "auto_badge"}
              className="mt-1"
            />
            <span>
              <strong>Fail-closed</strong> — new pipeline records stay in the review queue
              and are never public until a reviewer validates them.
            </span>
          </label>
          <label className="flex items-start gap-2">
            <input
              type="radio"
              name="publish_policy"
              value="auto_badge"
              defaultChecked={settings.publish_policy === "auto_badge"}
              className="mt-1"
            />
            <span>
              <strong>Auto-publish with &quot;unreviewed&quot; badge</strong> — new records go
              live immediately, marked unreviewed until validated.
            </span>
          </label>
        </fieldset>

        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            name="show_trends"
            defaultChecked={settings.show_trends === "1"}
          />
          <span className="font-medium">Show trends section on public page</span>
        </label>

        <label className="flex flex-col gap-1">
          <span className="font-medium">Cards per section</span>
          <input
            type="number"
            name="cards_per_section"
            min={1}
            max={100}
            defaultValue={settings.cards_per_section || "12"}
            className="w-32 rounded-md border px-2 py-1"
            style={{ borderColor: "var(--color-border)" }}
          />
        </label>

        <fieldset className="flex flex-col gap-2">
          <legend className="font-medium">Featured categories</legend>
          <p style={{ color: "var(--color-text-muted)" }}>
            Leave all unchecked to show all categories.
          </p>
          <div className="grid grid-cols-1 gap-1 sm:grid-cols-2">
            {TAXONOMY.map((c) => (
              <label key={c} className="flex items-center gap-2">
                <input
                  type="checkbox"
                  name="featured_categories"
                  value={c}
                  defaultChecked={featuredCategories.includes(c)}
                />
                <span>{c}</span>
              </label>
            ))}
          </div>
        </fieldset>

        <button
          type="submit"
          className="w-fit rounded-md px-4 py-2 font-medium"
          style={{ background: "var(--color-primary)", color: "var(--color-primary-contrast)" }}
        >
          Save settings
        </button>
      </form>
    </Card>
  );
}
