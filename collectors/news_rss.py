"""Healthtech news RSS collector.

Pulls recent articles from curated healthtech news feeds covering clinical
IT, digital health VC, and hospital ops.

The collector does NOT identify companies by itself. It returns raw article
records; the pipeline's entity resolver matches articles to existing
companies in the repository.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Optional

import feedparser

USER_AGENT = "Healthtech Dashboard 507webdev@gmail.com"

# Curated feeds. All free, all public. Add more over time.
# Note: Becker's Hospital Review blocks non-browser requests (403 on every UA we
# tried, incl. Chrome). Left out of the default list — consider a paid-scraper
# path later if Becker's coverage matters.
FEEDS: list[tuple[str, str]] = [
    ("MobiHealthNews", "https://www.mobihealthnews.com/rss.xml"),
    ("Fierce Healthcare", "https://www.fiercehealthcare.com/rss/xml"),
    ("Healthcare IT News", "https://www.healthcareitnews.com/feed"),
    ("Rock Health", "https://rockhealth.com/feed/"),
]


@dataclass
class Article:
    source: str  # feed name
    title: str
    url: str
    summary: Optional[str]
    published_at: Optional[str]  # ISO-8601 date (YYYY-MM-DD)


def _parse_published(entry) -> Optional[str]:
    for key in ("published_parsed", "updated_parsed"):
        parsed = getattr(entry, key, None)
        if parsed:
            try:
                dt = datetime(*parsed[:6], tzinfo=timezone.utc)
                return dt.date().isoformat()
            except (TypeError, ValueError):
                pass
    return None


def _strip_html(s: str) -> str:
    if not s:
        return ""
    # Feedparser already strips most tags in summary; this is a backstop.
    import re as _re
    return _re.sub(r"<[^>]+>", "", s).strip()


def collect(start: date, end: date) -> list[Article]:
    """Return articles with published_at in [start, end] across all feeds."""
    articles: list[Article] = []
    for feed_name, url in FEEDS:
        try:
            parsed = feedparser.parse(url, agent=USER_AGENT)
        except Exception as e:
            print(f"[news_rss] {feed_name} failed: {e}")
            continue
        if parsed.bozo and not parsed.entries:
            print(f"[news_rss] {feed_name} empty or unreadable")
            continue
        for entry in parsed.entries:
            pub = _parse_published(entry)
            if pub and not (start.isoformat() <= pub <= end.isoformat()):
                continue
            title = _strip_html(getattr(entry, "title", "")).strip()
            link = getattr(entry, "link", "").strip()
            if not title or not link:
                continue
            summary = _strip_html(getattr(entry, "summary", "") or getattr(entry, "description", ""))
            articles.append(Article(
                source=feed_name,
                title=title,
                url=link,
                summary=summary[:1000] if summary else None,
                published_at=pub,
            ))
        time.sleep(0.3)  # be polite between feeds
    return articles


if __name__ == "__main__":
    from datetime import timedelta
    end = date.today()
    start = end - timedelta(days=7)
    arts = collect(start, end)
    print(f"Got {len(arts)} articles from {start} to {end}")
    for a in arts[:5]:
        print(f"  [{a.published_at}] {a.source}: {a.title[:90]}")
