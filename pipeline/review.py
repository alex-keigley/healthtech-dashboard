"""Review queue writer.

Bias toward "hold for review" over false positives. For a healthcare-IT
audience, a single low-quality startup in the public repo costs more trust
than a few missed ones. This module scans the DB and writes a markdown
queue of candidates volunteers can work through via pull request.

Categories:
  - Untagged companies: classifier had no signal. A volunteer either confirms
    the company really is non-specific ("Other Health Care" holding co) or
    adds a tag manually.
  - Fuzzy-match candidates: pairs of companies with name similarity in the
    [0.75, 0.95) band. Above 0.95 is auto-merge; below 0.75 is noise. This
    band is where a human eye helps.
  - Recent low-confidence classifications: a company whose ONLY tags come
    from weak rules (max confidence < 0.7). The volunteer re-reads the
    company and either confirms or corrects.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from pipeline.entity_resolver import _TOO_GENERIC, similarity

REVIEW_DIR = Path(__file__).resolve().parent.parent / "review"


def _distinctive_tokens(canonical: str) -> set[str]:
    """Tokens worth identity-matching on: non-generic, longer than 2 chars."""
    if not canonical:
        return set()
    return {w for w in canonical.split() if w not in _TOO_GENERIC and len(w) > 2}


def _plausible_duplicate(a_canon: str, b_canon: str) -> bool:
    """Two names are plausibly the same company only if they share at least
    one distinctive token. `Alloy Therapeutics` vs `Bonum Therapeutics` share
    only 'therapeutics' (generic) — so they're NOT plausible duplicates even
    though SequenceMatcher rates them highly."""
    ta = _distinctive_tokens(a_canon)
    tb = _distinctive_tokens(b_canon)
    if not ta or not tb:
        return False
    return bool(ta & tb)


def _fmt_money(val) -> str:
    if val is None:
        return "—"
    try:
        v = float(val)
    except (TypeError, ValueError):
        return "—"
    if v >= 1_000_000:
        return f"${v/1_000_000:.1f}M"
    if v >= 1_000:
        return f"${v/1_000:.0f}K"
    return f"${v:,.0f}"


def _find_untagged(conn: sqlite3.Connection, limit: int = 30) -> list[dict]:
    rows = conn.execute(
        """
        SELECT c.id, c.name_display, c.state, c.focus, c.industry_group,
               c.first_surfaced_at,
               (SELECT MAX(f.total_offering_amount) FROM filings f WHERE f.company_id = c.id) AS largest_raise,
               (SELECT MAX(f.filing_url) FROM filings f WHERE f.company_id = c.id) AS filing_url
          FROM companies c
          LEFT JOIN tech_tags t ON t.company_id = c.id
         WHERE t.category IS NULL
         ORDER BY c.last_updated_at DESC
         LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def _find_low_confidence(conn: sqlite3.Connection,
                         threshold: float = 0.7,
                         limit: int = 30) -> list[dict]:
    rows = conn.execute(
        """
        SELECT c.id, c.name_display, c.state, c.focus,
               MAX(t.confidence) AS best_confidence,
               GROUP_CONCAT(t.category, ' | ') AS tags
          FROM companies c
          JOIN tech_tags t ON t.company_id = c.id
         GROUP BY c.id
        HAVING MAX(t.confidence) < ?
         ORDER BY best_confidence ASC
         LIMIT ?
        """,
        (threshold, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def _find_fuzzy_pairs(conn: sqlite3.Connection,
                      lo: float = 0.75, hi: float = 0.95,
                      limit: int = 30) -> list[dict]:
    """Pairwise compare canonical names and surface ambiguous matches.

    O(N^2) but we only have tens to hundreds of companies in Phase 3; we'll
    optimize with a blocking strategy when the repo grows.
    """
    rows = conn.execute(
        "SELECT id, name_display, name_canonical FROM companies ORDER BY name_canonical"
    ).fetchall()
    out: list[dict] = []
    for i, a in enumerate(rows):
        for b in rows[i + 1:]:
            if not _plausible_duplicate(a["name_canonical"], b["name_canonical"]):
                continue
            s = similarity(a["name_canonical"], b["name_canonical"])
            if lo <= s < hi:
                out.append({
                    "a_id": a["id"],
                    "b_id": b["id"],
                    "a_name": a["name_display"],
                    "b_name": b["name_display"],
                    "similarity": round(s, 3),
                })
                if len(out) >= limit:
                    return out
    return out


def generate(conn: sqlite3.Connection, out_dir: Path = REVIEW_DIR) -> Path:
    """Write review/pending.md. Returns the path."""
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "pending.md"

    untagged = _find_untagged(conn)
    low_conf = _find_low_confidence(conn)
    pairs = _find_fuzzy_pairs(conn)

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    lines: list[str] = []
    lines.append("# Review queue — pending")
    lines.append("")
    lines.append(f"_Generated {now} UTC._")
    lines.append("")
    lines.append(
        "This file holds candidates the automated pipeline couldn't classify "
        "confidently. Working it is how the repository stays trustworthy for a "
        "healthcare-IT audience. "
        "To resolve an item, open a pull request that edits the canonical data "
        "(company focus, technology tags, or a merge between two records) and "
        "delete the item from this list."
    )
    lines.append("")

    lines.append(f"## Untagged companies ({len(untagged)})")
    lines.append("")
    if untagged:
        lines.append(
            "These companies produced zero technology tags from the classifier. "
            "Either the company really is generic (e.g. a holding LLC) and should "
            "stay untagged, or a tag should be added manually."
        )
        lines.append("")
        lines.append("| Company | State | Focus | Industry group | Largest raise | Filing |")
        lines.append("|---|---|---|---|---:|---|")
        for r in untagged:
            link = f"[link]({r['filing_url']})" if r.get("filing_url") else "—"
            lines.append(
                f"| {r['name_display']} | {r.get('state') or '—'} | "
                f"{r.get('focus') or '—'} | {r.get('industry_group') or '—'} | "
                f"{_fmt_money(r.get('largest_raise'))} | {link} |"
            )
        lines.append("")
    else:
        lines.append("_No untagged companies. Classifier tagged everything._")
        lines.append("")

    lines.append(f"## Low-confidence classifications ({len(low_conf)})")
    lines.append("")
    if low_conf:
        lines.append(
            "These companies have tags, but the best rule fired below the 0.7 "
            "confidence bar. A volunteer should read the company's site and "
            "either confirm or correct the tag."
        )
        lines.append("")
        lines.append("| Company | State | Focus | Tags | Max confidence |")
        lines.append("|---|---|---|---|---:|")
        for r in low_conf:
            lines.append(
                f"| {r['name_display']} | {r.get('state') or '—'} | "
                f"{r.get('focus') or '—'} | {r.get('tags') or '—'} | "
                f"{r['best_confidence']:.2f} |"
            )
        lines.append("")
    else:
        lines.append("_No low-confidence classifications._")
        lines.append("")

    lines.append(f"## Fuzzy-match candidates ({len(pairs)})")
    lines.append("")
    if pairs:
        lines.append(
            "Pairs of companies whose canonical names are 75–95% similar. If they "
            "are the same entity, merge via pull request (keep the earlier "
            "`first_funded_at`/`first_surfaced_at`, combine filings, aliases)."
        )
        lines.append("")
        lines.append("| A | B | Similarity |")
        lines.append("|---|---|---:|")
        for p in pairs:
            lines.append(
                f"| {p['a_name']} (#{p['a_id']}) | {p['b_name']} (#{p['b_id']}) | "
                f"{p['similarity']:.3f} |"
            )
        lines.append("")
    else:
        lines.append("_No fuzzy-match candidates in the 0.75–0.95 band._")
        lines.append("")

    out.write_text("\n".join(lines), encoding="utf-8")
    return out
