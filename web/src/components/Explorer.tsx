"use client";

import { useMemo, useState } from "react";
import CompanyCard, { type CompanyCardData } from "@/components/CompanyCard";
import { TAXONOMY } from "@/lib/taxonomy";

export interface ExplorerCompany extends CompanyCardData {
  name_canonical: string;
  description: string | null;
  first_surfaced_at: string;
}

type SortMode = "newest" | "alphabetical" | "raise";

export default function Explorer({ companies }: { companies: ExplorerCompany[] }) {
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const [state, setState] = useState("");
  const [sort, setSort] = useState<SortMode>("newest");

  const states = useMemo(() => {
    const set = new Set<string>();
    for (const c of companies) {
      if (c.state) set.add(c.state);
    }
    return Array.from(set).sort();
  }, [companies]);

  const filtered = useMemo(() => {
    let result = companies;

    if (search.trim()) {
      const q = search.trim().toLowerCase();
      result = result.filter(
        (c) =>
          c.name_display.toLowerCase().includes(q) ||
          (c.description ? c.description.toLowerCase().includes(q) : false)
      );
    }

    if (category) {
      result = result.filter((c) => c.tags.includes(category));
    }

    if (state) {
      result = result.filter((c) => c.state === state);
    }

    const sorted = [...result];
    if (sort === "newest") {
      sorted.sort(
        (a, b) => new Date(b.first_surfaced_at).getTime() - new Date(a.first_surfaced_at).getTime()
      );
    } else if (sort === "alphabetical") {
      sorted.sort((a, b) => a.name_display.localeCompare(b.name_display));
    } else if (sort === "raise") {
      sorted.sort((a, b) => (b.largestRaise ?? 0) - (a.largestRaise ?? 0));
    }

    return sorted;
  }, [companies, search, category, state, sort]);

  if (companies.length === 0) {
    return (
      <p className="text-center" style={{ color: "var(--color-text-muted)" }}>
        No published companies yet — records are awaiting human review.
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap gap-3">
        <input
          type="search"
          placeholder="Search companies…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="min-w-[200px] flex-1 rounded-md border px-3 py-2 text-sm"
          style={{ borderColor: "var(--color-border)", background: "var(--color-surface)", color: "var(--color-text)" }}
        />
        <select
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          className="rounded-md border px-3 py-2 text-sm"
          style={{ borderColor: "var(--color-border)", background: "var(--color-surface)", color: "var(--color-text)" }}
        >
          <option value="">All categories</option>
          {TAXONOMY.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        <select
          value={state}
          onChange={(e) => setState(e.target.value)}
          className="rounded-md border px-3 py-2 text-sm"
          style={{ borderColor: "var(--color-border)", background: "var(--color-surface)", color: "var(--color-text)" }}
        >
          <option value="">All states</option>
          {states.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <select
          value={sort}
          onChange={(e) => setSort(e.target.value as SortMode)}
          className="rounded-md border px-3 py-2 text-sm"
          style={{ borderColor: "var(--color-border)", background: "var(--color-surface)", color: "var(--color-text)" }}
        >
          <option value="newest">Newest first</option>
          <option value="alphabetical">Name (A–Z)</option>
          <option value="raise">Largest raise</option>
        </select>
      </div>

      {filtered.length === 0 ? (
        <p className="text-center" style={{ color: "var(--color-text-muted)" }}>
          No companies match these filters.
        </p>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((company) => (
            <CompanyCard key={company.id} company={company} />
          ))}
        </div>
      )}
    </div>
  );
}
