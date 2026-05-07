"""Healthtech Startup Dashboard.

Reads data/startups.db directly. Pages:
  - Overview: hero numbers + recent Form D filings table
  - Startup Explorer: every tracked company with technology tags, filters,
    and a per-company detail pane showing news articles and tag confidences.
  - Trends: weekly filing volume, state distribution, raise-size histogram.
  - Technology Lens: per-category deep dive.
  - Weekly report: auto-generated markdown summary.
  - Review queue: items held for manual classification.
  - Methodology: public methodology document.

Run:  streamlit run app.py
"""

from __future__ import annotations

import html
import re
from datetime import date, timedelta
from urllib.parse import quote_plus

import pandas as pd
import streamlit as st

from pipeline import db

st.set_page_config(
    page_title="Healthtech Startup Dashboard",
    page_icon=":hospital:",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Hide the empty sidebar completely (we navigate via st.tabs instead) and
# tighten the tab bar + card styling for a calmer, light-themed look.
st.markdown(
    """
    <style>
      section[data-testid="stSidebar"] { display: none !important; }
      button[data-testid="collapsedControl"] { display: none !important; }
      button[data-testid="stSidebarCollapsedControl"] { display: none !important; }

      /* Tighten top padding now that the sidebar is gone. */
      section.main > div.block-container { padding-top: 1.2rem; }

      /* Make tabs feel like primary navigation rather than a minor control. */
      div[data-baseweb="tab-list"] {
          gap: 0.25rem;
          border-bottom: 1px solid #E5E7EB;
      }
      button[data-baseweb="tab"] {
          font-size: 0.98rem !important;
          padding: 0.55rem 1.1rem !important;
          color: #374151 !important;
      }
      button[data-baseweb="tab"][aria-selected="true"] {
          color: #0B5394 !important;
          font-weight: 600 !important;
      }

      /* Card-like metric panels. */
      div[data-testid="stMetric"] {
          background: #F4F6FA;
          border: 1px solid #E5E7EB;
          border-radius: 8px;
          padding: 0.75rem 1rem;
      }
    </style>
    """,
    unsafe_allow_html=True,
)


def _urlquote(s: str) -> str:
    return quote_plus(s)


def _money(val) -> str:
    if val is None or pd.isna(val):
        return "—"
    if val >= 1_000_000:
        return f"${val/1_000_000:.1f}M"
    if val >= 1_000:
        return f"${val/1_000:.0f}K"
    return f"${val:,.0f}"


@st.cache_data(ttl=300)
def load_filings() -> pd.DataFrame:
    if not db.DB_PATH.exists():
        return pd.DataFrame()
    with db.connect() as conn:
        df = pd.read_sql_query(
            """
            SELECT c.id AS company_id,
                   c.name_display AS company,
                   c.focus,
                   c.state,
                   c.industry_group,
                   c.entity_type,
                   c.year_of_inc,
                   f.filing_date,
                   f.date_of_first_sale,
                   f.total_offering_amount,
                   f.filing_url,
                   f.accession,
                   f.observed_at
              FROM filings f
              JOIN companies c ON c.id = f.company_id
             ORDER BY f.filing_date DESC, f.accession DESC
            """,
            conn,
        )
    if not df.empty:
        df["filing_date"] = pd.to_datetime(df["filing_date"], errors="coerce").dt.date
        df["observed_at"] = pd.to_datetime(df["observed_at"], errors="coerce")
        df["search_url"] = df["company"].apply(
            lambda n: f"https://duckduckgo.com/?q={_urlquote(n + ' healthcare')}"
        )
    return df


@st.cache_data(ttl=300)
def load_companies_with_tags() -> pd.DataFrame:
    """One row per company, with tags as a pipe-joined string and article count."""
    if not db.DB_PATH.exists():
        return pd.DataFrame()
    with db.connect() as conn:
        df = pd.read_sql_query(
            """
            SELECT c.id AS company_id,
                   c.name_display AS company,
                   c.focus,
                   c.state,
                   c.industry_group,
                   c.entity_type,
                   c.year_of_inc,
                   c.first_surfaced_at,
                   c.first_funded_at,
                   c.last_updated_at,
                   (SELECT GROUP_CONCAT(t.category, ' | ')
                      FROM (SELECT category FROM tech_tags
                             WHERE company_id = c.id
                             ORDER BY confidence DESC) t) AS tags,
                   (SELECT COUNT(*) FROM articles a WHERE a.company_id = c.id) AS article_count,
                   (SELECT COUNT(*) FROM filings f WHERE f.company_id = c.id) AS filing_count,
                   (SELECT MAX(f.total_offering_amount)
                      FROM filings f WHERE f.company_id = c.id) AS largest_raise
              FROM companies c
            """,
            conn,
        )
    if not df.empty:
        df["search_url"] = df["company"].apply(
            lambda n: f"https://duckduckgo.com/?q={_urlquote(n + ' healthcare')}"
        )
        df["first_funded_at"] = pd.to_datetime(df["first_funded_at"], errors="coerce").dt.date
        df["first_surfaced_dt"] = pd.to_datetime(
            df["first_surfaced_at"], errors="coerce", utc=True
        )
    return df


@st.cache_data(ttl=300)
def load_company_detail(company_id: int) -> dict:
    if not db.DB_PATH.exists():
        return {}
    with db.connect() as conn:
        company = conn.execute(
            "SELECT * FROM companies WHERE id = ?", (company_id,)
        ).fetchone()
        if not company:
            return {}
        tags = conn.execute(
            "SELECT category, confidence FROM tech_tags WHERE company_id = ? "
            "ORDER BY confidence DESC",
            (company_id,),
        ).fetchall()
        articles = conn.execute(
            "SELECT source, title, url, summary, published_at FROM articles "
            "WHERE company_id = ? ORDER BY published_at DESC",
            (company_id,),
        ).fetchall()
        filings = conn.execute(
            "SELECT filing_date, total_offering_amount, filing_url, accession "
            "FROM filings WHERE company_id = ? ORDER BY filing_date DESC",
            (company_id,),
        ).fetchall()
    return {
        "company": dict(company),
        "tags": [dict(r) for r in tags],
        "articles": [dict(r) for r in articles],
        "filings": [dict(r) for r in filings],
    }


@st.cache_data(ttl=300)
def load_top_recent_companies(days: int = 30, limit: int = 12) -> pd.DataFrame:
    """Top funded companies in the last N days, with description + tags + filing.

    Powers the Overview hero. One row per company; ranked by largest raise.
    """
    if not db.DB_PATH.exists():
        return pd.DataFrame()
    today = date.today()
    since = (today - timedelta(days=days)).isoformat()
    with db.connect() as conn:
        df = pd.read_sql_query(
            """
            SELECT c.id AS company_id,
                   c.name_display AS company,
                   c.state,
                   c.industry_group,
                   c.entity_type,
                   c.focus,
                   c.year_of_inc,
                   MAX(f.total_offering_amount) AS largest_raise,
                   MAX(f.filing_date) AS latest_filing_date,
                   (SELECT f2.filing_url FROM filings f2
                     WHERE f2.company_id = c.id
                       AND f2.total_offering_amount IS NOT NULL
                     ORDER BY f2.total_offering_amount DESC,
                              f2.filing_date DESC LIMIT 1) AS filing_url,
                   (SELECT GROUP_CONCAT(t.category, '|')
                      FROM (SELECT category FROM tech_tags
                             WHERE company_id = c.id
                             ORDER BY confidence DESC) t) AS tags,
                   cd.description AS scraped_desc,
                   cd.url AS scraped_url,
                   cd.source AS scraped_source
              FROM companies c
              JOIN filings f ON f.company_id = c.id
              LEFT JOIN company_descriptions cd ON cd.company_id = c.id
             WHERE f.filing_date >= ?
             GROUP BY c.id
             ORDER BY largest_raise DESC, c.name_display
             LIMIT ?
            """,
            conn,
            params=(since, limit),
        )
    return df


@st.cache_data(ttl=300)
def all_known_categories() -> list[str]:
    if not db.DB_PATH.exists():
        return []
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT DISTINCT category FROM tech_tags ORDER BY category"
        ).fetchall()
    return [r["category"] for r in rows]


def _page_overview(filings: pd.DataFrame, companies: pd.DataFrame) -> None:
    if filings.empty and companies.empty:
        st.warning(
            "No data yet. Populate the store with:  \n"
            "`python -m pipeline.run --days 7`"
        )
        return

    # --- Anchor "this week" to the most recent ingest, not the wall-clock
    # date. If the last pipeline run was 12 days ago, anchoring to today
    # would show 0 / 0 / 0 and look broken — when in reality those zeros
    # are an artefact of staleness, not a property of the data window.
    anchor: date = date.today()
    if not filings.empty and not filings["observed_at"].isna().all():
        anchor = filings["observed_at"].max().date()
    week_ago = anchor - timedelta(days=7)
    current_year = str(anchor.year)

    # --- Compact metric strip --------------------------------------------
    # Three "new" signals + repository total. The hero on this page is the
    # top-companies list below; the metrics are a header, not a chart.
    if not filings.empty:
        funded_this_week = filings[filings["filing_date"] >= week_ago]
        new_funded = int(funded_this_week["company_id"].nunique())
        founded_mask = funded_this_week["year_of_inc"].fillna("").astype(str) == current_year
        new_founded = int(funded_this_week.loc[founded_mask, "company_id"].nunique())
    else:
        new_funded = new_founded = 0

    if not companies.empty and "first_surfaced_dt" in companies.columns:
        week_ago_ts = pd.Timestamp(week_ago, tz="UTC")
        new_surfaced = int((companies["first_surfaced_dt"] >= week_ago_ts).sum())
    else:
        new_surfaced = 0

    companies_total = int(companies.shape[0]) if not companies.empty else 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Newly funded · 7d", f"{new_funded:,}")
    col2.metric("Newly surfaced · 7d", f"{new_surfaced:,}")
    col3.metric("Newly founded · 7d", f"{new_founded:,}")
    col4.metric("Repository", f"{companies_total:,}")
    st.caption(
        f"7-day window anchored on the latest pipeline run "
        f"({anchor.strftime('%b %d, %Y').replace(' 0', ' ')})."
    )

    st.divider()

    # --- Hero: top healthtech companies in the past 30 days --------------
    st.subheader("Top healthtech companies — past 30 days")
    st.caption(
        "Ranked by largest Form D raise. Each description is sourced either "
        "from a recent news article or from the company website's meta "
        "description (verified to mention the company by name)."
    )

    top = load_top_recent_companies(days=30, limit=12)
    if top.empty:
        st.info(
            "No funded healthtech companies in the last 30 days. Run "
            "`python -m pipeline.run --days 30` to refresh the data."
        )
    else:
        for _, r in top.iterrows():
            _render_company_card(r)

    # --- Footer ----------------------------------------------------------
    st.divider()
    reports_dir = REPO_ROOT / "reports"
    reports = sorted(reports_dir.glob("*.md"), reverse=True) if reports_dir.exists() else []
    bits = []
    if reports:
        bits.append(
            f"**Latest weekly report:** `{reports[0].stem}` — open the "
            "*Weekly report* tab to read it."
        )
    if not filings.empty and not filings["observed_at"].isna().all():
        last_observed = filings["observed_at"].max()
        bits.append(f"**Last pipeline run:** {last_observed:%Y-%m-%d %H:%M UTC}")
    bits.append(
        "Use the **Startup Explorer** tab for the full repository, or "
        "**Trends** for charts."
    )
    for b in bits:
        st.caption(b)


def _render_company_card(row: pd.Series) -> None:
    """Render one company highlight card on the Overview page."""
    def _normalize_text(value) -> str:
        if value is None or pd.isna(value):
            return ""
        return str(value).strip()

    description = _normalize_text(row.get("scraped_desc"))
    if description:
        # Belt-and-braces: catch any HTML entities or stray U+FFFD that
        # slipped through the scraper before we improved its cleaner.
        description = html.unescape(description).replace("�", "")
    if not description:
        focus = _normalize_text(row.get("focus"))
        if focus:
            description = f"_{focus}_ — no scraped description yet."
        else:
            description = "_No description available — see the company's filing for details._"

    raise_str = _money(row.get("largest_raise"))
    name = row.get("company") or "(unknown)"

    with st.container(border=True):
        head_left, head_right = st.columns([5, 1])
        with head_left:
            st.markdown(f"#### {name}")
            meta_bits = []
            if row.get("state"):
                meta_bits.append(str(row["state"]))
            if row.get("industry_group"):
                meta_bits.append(str(row["industry_group"]))
            if row.get("entity_type"):
                meta_bits.append(str(row["entity_type"]))
            if row.get("year_of_inc"):
                meta_bits.append(f"inc. {row['year_of_inc']}")
            if row.get("latest_filing_date"):
                meta_bits.append(f"filed {row['latest_filing_date']}")
            if meta_bits:
                st.caption(" · ".join(meta_bits))
        with head_right:
            st.markdown(
                f"<div style='text-align:right;font-size:1.5rem;"
                f"font-weight:600;color:#0B5394;line-height:1.1'>{raise_str}</div>"
                f"<div style='text-align:right;color:#6B7280;font-size:0.85rem'>"
                f"largest raise</div>",
                unsafe_allow_html=True,
            )

        st.write(description)

        # Technology tag chips
        tags_raw = row.get("tags")
        if isinstance(tags_raw, list):
            tags = [str(t).strip() for t in tags_raw if str(t).strip()]
        else:
            tags_str = "" if pd.isna(tags_raw) else str(tags_raw)
            tags = [t.strip() for t in tags_str.split("|") if t.strip()]
        if tags:
            chips = " ".join(f":blue-background[{t}]" for t in tags[:6])
            st.markdown(chips)

        # Source links
        link_bits = []
        if row.get("filing_url"):
            link_bits.append(f"[SEC Form D]({row['filing_url']})")
        scraped_url = row.get("scraped_url")
        scraped_source = row.get("scraped_source")
        if scraped_url:
            label = "News article" if scraped_source == "news" else "Company site"
            link_bits.append(f"[{label}]({scraped_url})")
        search_url = (
            f"https://duckduckgo.com/?q={_urlquote((name or '') + ' healthcare')}"
        )
        link_bits.append(f"[Web search]({search_url})")
        st.caption(" · ".join(link_bits))


def _page_explorer(companies: pd.DataFrame) -> None:
    st.caption(
        "Every tracked US healthtech company with its technology tags, "
        "source activity, and links. Filter by category, state, or industry; select a row "
        "below the table to view details."
    )

    if companies.empty:
        st.warning(
            "No companies tracked yet. Populate the store with:  \n"
            "`python -m pipeline.run --days 7`"
        )
        return

    categories = all_known_categories()
    industries = sorted([i for i in companies["industry_group"].dropna().unique()])
    states = sorted([s for s in companies["state"].dropna().unique()])

    filt_col1, filt_col2, filt_col3 = st.columns(3)
    with filt_col1:
        picked_categories = st.multiselect("Technology category", categories, default=[])
    with filt_col2:
        picked_industries = st.multiselect("Industry group", industries, default=[])
    with filt_col3:
        picked_states = st.multiselect("State", states, default=[])

    filtered = companies.copy()
    if picked_industries:
        filtered = filtered[filtered["industry_group"].isin(picked_industries)]
    if picked_states:
        filtered = filtered[filtered["state"].isin(picked_states)]
    if picked_categories:
        pattern = "|".join(re.escape(c) for c in picked_categories)
        filtered = filtered[filtered["tags"].fillna("").str.contains(pattern, regex=True)]

    tagged = filtered[filtered["tags"].fillna("") != ""]
    with_news = filtered[filtered["article_count"] > 0]
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Companies (filtered)", f"{len(filtered):,}")
    col2.metric("With technology tags", f"{len(tagged):,}")
    col3.metric("With news articles", f"{len(with_news):,}")
    col4.metric("Distinct states", f"{filtered['state'].nunique():,}")

    st.divider()

    display = filtered[[
        "company", "focus", "tags", "industry_group", "state", "entity_type",
        "year_of_inc", "first_funded_at", "largest_raise", "article_count",
        "filing_count", "search_url",
    ]].copy()
    display["largest_raise"] = display["largest_raise"].apply(_money)
    display = display.rename(columns={
        "company": "Company",
        "focus": "Likely focus",
        "tags": "Technology tags",
        "industry_group": "Industry",
        "state": "State",
        "entity_type": "Entity",
        "year_of_inc": "Year inc.",
        "first_funded_at": "First funded",
        "largest_raise": "Largest raise",
        "article_count": "News",
        "filing_count": "Filings",
        "search_url": "Search",
    })

    st.dataframe(
        display,
        hide_index=True,
        use_container_width=True,
        column_config={
            "Company": st.column_config.TextColumn(width="medium"),
            "Likely focus": st.column_config.TextColumn(width="medium"),
            "Technology tags": st.column_config.TextColumn(width="large"),
            "Largest raise": st.column_config.TextColumn(width="small"),
            "News": st.column_config.NumberColumn(width="small"),
            "Filings": st.column_config.NumberColumn(width="small"),
            "Search": st.column_config.LinkColumn("Search", display_text="look up"),
        },
    )

    st.download_button(
        "Download filtered list (CSV)",
        data=filtered.to_csv(index=False).encode("utf-8"),
        file_name="healthtech_companies.csv",
        mime="text/csv",
    )

    st.divider()
    st.subheader("Company detail")
    options = filtered.sort_values("company")[["company_id", "company"]]
    if options.empty:
        st.info("No companies in the current filter.")
        return
    picked = st.selectbox(
        "Select a company",
        options=options["company_id"].tolist(),
        format_func=lambda cid: options.set_index("company_id").loc[cid, "company"],
    )
    if picked is not None:
        _render_company_detail(int(picked))


def _render_company_detail(company_id: int) -> None:
    detail = load_company_detail(company_id)
    if not detail:
        st.info("Company not found.")
        return
    c = detail["company"]
    tags = detail["tags"]
    articles = detail["articles"]
    filings = detail["filings"]

    st.markdown(f"### {c['name_display']}")
    meta_bits = []
    if c.get("state"):
        meta_bits.append(c["state"])
    if c.get("entity_type"):
        meta_bits.append(c["entity_type"])
    if c.get("year_of_inc"):
        meta_bits.append(f"inc. {c['year_of_inc']}")
    if c.get("industry_group"):
        meta_bits.append(c["industry_group"])
    if meta_bits:
        st.caption(" · ".join(meta_bits))
    if c.get("focus"):
        st.write(f"**Likely focus:** {c['focus']}")
    search_url = f"https://duckduckgo.com/?q={_urlquote((c['name_display'] or '') + ' healthcare')}"
    st.markdown(f"[Search the web for this company]({search_url})")

    left, right = st.columns(2)
    with left:
        st.markdown("**Technology tags**")
        if tags:
            st.dataframe(
                pd.DataFrame(tags).rename(columns={"category": "Category", "confidence": "Confidence"}),
                hide_index=True,
                use_container_width=True,
            )
        else:
            st.caption("No technology tags yet — classifier had no strong signal in available text.")

        st.markdown("**Form D filings**")
        if filings:
            fdf = pd.DataFrame(filings)
            fdf["total_offering_amount"] = fdf["total_offering_amount"].apply(_money)
            fdf = fdf.rename(columns={
                "filing_date": "Filed",
                "total_offering_amount": "Raise",
                "filing_url": "EDGAR",
                "accession": "Accession",
            })
            st.dataframe(
                fdf,
                hide_index=True,
                use_container_width=True,
                column_config={
                    "EDGAR": st.column_config.LinkColumn("EDGAR", display_text="link"),
                },
            )
        else:
            st.caption("No Form D filings recorded.")

    with right:
        st.markdown("**News articles**")
        if articles:
            for art in articles:
                date_str = art.get("published_at") or "—"
                src = art.get("source") or "news"
                title = art.get("title") or "(untitled)"
                url = art.get("url") or "#"
                summary = art.get("summary") or ""
                st.markdown(f"**[{title}]({url})**  \n`{date_str}` · *{src}*")
                if summary:
                    st.caption(summary[:400] + ("…" if len(summary) > 400 else ""))
                st.write("")
        else:
            st.caption("No news articles attached to this company yet.")


REPO_ROOT = db.DB_PATH.parent.parent


@st.cache_data(ttl=300)
def load_weekly_filings(weeks: int = 12) -> pd.DataFrame:
    """Filing counts bucketed by ISO week for the last N weeks."""
    if not db.DB_PATH.exists():
        return pd.DataFrame()
    with db.connect() as conn:
        df = pd.read_sql_query(
            """
            SELECT filing_date
              FROM filings
             WHERE filing_date IS NOT NULL
            """,
            conn,
        )
    if df.empty:
        return df
    df["filing_date"] = pd.to_datetime(df["filing_date"], errors="coerce")
    df = df.dropna(subset=["filing_date"])
    df["week_start"] = df["filing_date"].dt.to_period("W-SUN").apply(
        lambda p: p.start_time.date()
    )
    counts = df.groupby("week_start").size().reset_index(name="filings")
    counts = counts.sort_values("week_start").tail(weeks)
    return counts


@st.cache_data(ttl=300)
def load_category_companies(category: str) -> pd.DataFrame:
    if not db.DB_PATH.exists() or not category:
        return pd.DataFrame()
    with db.connect() as conn:
        df = pd.read_sql_query(
            """
            SELECT c.id AS company_id,
                   c.name_display AS company,
                   c.focus,
                   c.state,
                   c.industry_group,
                   c.first_funded_at,
                   t.confidence,
                   (SELECT MAX(f.total_offering_amount)
                      FROM filings f WHERE f.company_id = c.id) AS largest_raise,
                   (SELECT COUNT(*) FROM filings f WHERE f.company_id = c.id) AS filing_count,
                   (SELECT COUNT(*) FROM articles a WHERE a.company_id = c.id) AS article_count
              FROM companies c
              JOIN tech_tags t ON t.company_id = c.id
             WHERE t.category = ?
             ORDER BY t.confidence DESC, c.name_display
            """,
            conn,
            params=(category,),
        )
    return df


@st.cache_data(ttl=300)
def load_category_articles(category: str, limit: int = 10) -> pd.DataFrame:
    if not db.DB_PATH.exists() or not category:
        return pd.DataFrame()
    with db.connect() as conn:
        df = pd.read_sql_query(
            """
            SELECT a.title, a.url, a.source, a.published_at,
                   c.name_display AS company
              FROM articles a
              JOIN companies c ON c.id = a.company_id
              JOIN tech_tags t ON t.company_id = c.id
             WHERE t.category = ?
             ORDER BY a.published_at DESC
             LIMIT ?
            """,
            conn,
            params=(category, limit),
        )
    return df


def _page_trends(filings: pd.DataFrame, companies: pd.DataFrame) -> None:
    st.caption(
        "Weekly filing volume, geographic distribution, and raise-size histogram "
        "across the full tracking window."
    )
    if filings.empty:
        st.warning("No filings yet. Run the pipeline first.")
        return

    st.subheader("Weekly filing volume (last 12 weeks)")
    weekly = load_weekly_filings(weeks=12)
    if weekly.empty:
        st.info("Not enough data for a weekly chart yet.")
    else:
        chart_df = weekly.set_index("week_start")
        st.line_chart(chart_df, y="filings", height=280)
        st.caption(
            f"{int(weekly['filings'].sum()):,} total filings across "
            f"{len(weekly)} weeks; weekly mean "
            f"{weekly['filings'].mean():.1f}."
        )

    st.divider()
    st.subheader("Companies by state (top 15)")
    if companies.empty:
        st.info("No company data.")
    else:
        state_counts = (
            companies[companies["state"].notna() & (companies["filing_count"] > 0)]
            .groupby("state")
            .size()
            .reset_index(name="companies")
            .sort_values("companies", ascending=False)
            .head(15)
        )
        if state_counts.empty:
            st.info("No state-level data to chart.")
        else:
            st.bar_chart(state_counts.set_index("state"), y="companies", height=320)

    st.divider()
    st.subheader("Raise size distribution")
    raises = filings[filings["total_offering_amount"].notna()][
        "total_offering_amount"
    ].astype(float)
    if raises.empty:
        st.info("No raise amounts reported.")
    else:
        bins = [0, 500_000, 1_000_000, 5_000_000, 10_000_000, 25_000_000,
                50_000_000, 100_000_000, float("inf")]
        labels = ["<$500K", "$500K-1M", "$1M-5M", "$5M-10M", "$10M-25M",
                  "$25M-50M", "$50M-100M", ">$100M"]
        buckets = pd.cut(raises, bins=bins, labels=labels, right=False)
        counts = buckets.value_counts().reindex(labels).fillna(0).astype(int)
        st.bar_chart(counts, y=counts.name, height=280)
        col1, col2, col3 = st.columns(3)
        col1.metric("Filings with amount", f"{len(raises):,}")
        col2.metric("Median raise", _money(raises.median()))
        col3.metric("Largest raise", _money(raises.max()))


def _page_technology_lens(companies: pd.DataFrame) -> None:
    st.caption(
        "Per-category view: who's in it, what they raise, and what the "
        "healthtech press is saying. Categories follow widely used industry "
        "groupings."
    )
    categories = all_known_categories()
    if not categories:
        st.warning(
            "No technology tags in the database yet. Run `python -m pipeline.run` "
            "so the classifier can populate tags."
        )
        return

    category = st.selectbox("Technology category", options=categories)
    if not category:
        return

    cat_companies = load_category_companies(category)
    cat_articles = load_category_articles(category)

    filed_only = cat_companies[cat_companies["filing_count"] > 0]
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Companies in category", f"{len(cat_companies):,}")
    col2.metric("With filings", f"{len(filed_only):,}")
    raises = filed_only["largest_raise"].dropna().astype(float)
    col3.metric("Median raise", _money(raises.median()) if not raises.empty else "—")
    col4.metric("Largest raise", _money(raises.max()) if not raises.empty else "—")

    st.divider()
    st.subheader("Companies")
    if cat_companies.empty:
        st.info("No companies tagged in this category.")
    else:
        display = cat_companies[[
            "company", "focus", "state", "industry_group", "first_funded_at",
            "largest_raise", "filing_count", "article_count", "confidence",
        ]].copy()
        display["largest_raise"] = display["largest_raise"].apply(_money)
        display = display.rename(columns={
            "company": "Company",
            "focus": "Likely focus",
            "state": "State",
            "industry_group": "Industry",
            "first_funded_at": "First funded",
            "largest_raise": "Largest raise",
            "filing_count": "Filings",
            "article_count": "News",
            "confidence": "Tag conf.",
        })
        st.dataframe(
            display,
            hide_index=True,
            use_container_width=True,
            column_config={
                "Tag conf.": st.column_config.NumberColumn(format="%.2f"),
                "Filings": st.column_config.NumberColumn(width="small"),
                "News": st.column_config.NumberColumn(width="small"),
            },
        )

    st.subheader("Recent news in this category")
    if cat_articles.empty:
        st.caption(
            "No news articles attached to companies in this category yet. "
            "This is expected while the seed list is small; news matching "
            "grows as the repository does."
        )
    else:
        for _, a in cat_articles.iterrows():
            date_str = a.get("published_at") or "—"
            st.markdown(
                f"**[{a['title']}]({a['url']})**  \n"
                f"`{date_str}` · *{a['source']}* — mentions **{a['company']}**"
            )


def _page_weekly_report() -> None:
    st.caption(
        "Auto-generated markdown summary of each week's activity — the same "
        "content designed for emailing to a healthcare-IT distribution list."
    )
    reports_dir = REPO_ROOT / "reports"
    if not reports_dir.exists():
        st.warning("No reports yet. Run `python -m pipeline.run --days 7` to generate one.")
        return
    reports = sorted(reports_dir.glob("*.md"), reverse=True)
    if not reports:
        st.warning("No weekly reports found in `reports/`.")
        return
    picked = st.selectbox(
        "Week starting",
        options=[p.stem for p in reports],
    )
    path = reports_dir / f"{picked}.md"
    if path.exists():
        st.markdown(path.read_text(encoding="utf-8"))


def _page_methodology() -> None:
    st.caption(
        "The public methodology document — read this first if you're evaluating the "
        "dashboard."
    )
    path = REPO_ROOT / "METHODOLOGY.md"
    if not path.exists():
        st.warning("`METHODOLOGY.md` not found at the repository root.")
        return
    st.markdown(path.read_text(encoding="utf-8"))


def _page_review_queue() -> None:
    st.caption(
        "Candidates the automated pipeline couldn't classify confidently — "
        "the workflow that keeps the repository trustworthy."
    )
    path = REPO_ROOT / "review" / "pending.md"
    if not path.exists():
        st.info(
            "No review queue yet. Run `python -m pipeline.run` to generate one, or "
            "the queue is genuinely empty (everything resolved)."
        )
        return
    st.markdown(path.read_text(encoding="utf-8"))


def _render_header(filings: pd.DataFrame) -> None:
    """App-wide brand strip shown above the tab bar."""
    last_ingest = None
    if not filings.empty and not filings["observed_at"].isna().all():
        last_ingest = filings["observed_at"].max()

    left, right = st.columns([4, 1])
    with left:
        st.markdown(
            "#### :hospital: Healthtech Startup Dashboard"
        )
        st.caption(
            "Weekly US healthtech startup tracker. Every data point traces "
            "to a public SEC filing or RSS feed."
        )
    with right:
        if last_ingest is not None:
            st.caption(
                f"<div style='text-align:right; color:#6B7280;'>"
                f"<strong>Last ingest</strong><br>{last_ingest:%Y-%m-%d %H:%M} UTC"
                f"</div>",
                unsafe_allow_html=True,
            )


def main() -> None:
    filings = load_filings()
    companies = load_companies_with_tags()

    _render_header(filings)

    tab_labels = [
        "Overview",
        "Startup Explorer",
        "Trends",
        "Technology Lens",
        "Weekly Report",
        "Review Queue",
        "Methodology",
    ]
    tabs = st.tabs(tab_labels)

    with tabs[0]:
        _page_overview(filings, companies)
    with tabs[1]:
        _page_explorer(companies)
    with tabs[2]:
        _page_trends(filings, companies)
    with tabs[3]:
        _page_technology_lens(companies)
    with tabs[4]:
        _page_weekly_report()
    with tabs[5]:
        _page_review_queue()
    with tabs[6]:
        _page_methodology()


if __name__ == "__main__":
    main()
