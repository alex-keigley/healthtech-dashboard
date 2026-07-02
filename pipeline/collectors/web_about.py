"""Resolve a company's likely website and extract a short description.

We search Mojeek (an independent search engine that doesn't aggressively
block automated lookups the way DuckDuckGo does), pick the most plausible
organic result, then fetch that page and pull a description from standard
meta tags. The intent is to populate the dashboard's "what they offer"
field for companies the news feed didn't already describe.

Quality gate: a wrong description is much worse than no description (a
healthcare-IT audience will lose trust on the first hallucination), so
`lookup` walks the top-N ranked candidates and verifies each fetched page
before accepting. Verification requires the page title to mention the
company's distinctive token AND not be a terms/privacy/cookie sub-page.

The scraper is regex-based on purpose — adding BeautifulSoup just to read
two `<meta>` tags is overkill, and we don't want to take on a dependency
the rest of the pipeline doesn't need.

Politeness: identifying user-agent, sequential GETs with caller-controlled
delay between hosts. Failures degrade silently to None — the dashboard
falls back to the heuristic focus label.
"""

from __future__ import annotations

import html
import re
import time
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

import requests

UA = "Mozilla/5.0 (compatible; Healthtech-Dashboard/1.0)"

MOJEEK_URL = "https://www.mojeek.com/search"

# Mojeek's organic results carry class="ob" on the result anchor. The href
# is the destination URL directly — no redirect wrapping.
_RESULT_HREF = re.compile(
    r'<a[^>]+href="(https?://[^"]+)"[^>]*class="[^"]*\bob\b[^"]*"',
    re.IGNORECASE,
)

# Meta description in either attribute order.
_META_DESC_FWD = re.compile(
    r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']',
    re.IGNORECASE,
)
_META_DESC_REV = re.compile(
    r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']description["\']',
    re.IGNORECASE,
)
_OG_DESC_FWD = re.compile(
    r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']',
    re.IGNORECASE,
)
_OG_DESC_REV = re.compile(
    r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:description["\']',
    re.IGNORECASE,
)
_TITLE = re.compile(r"<title[^>]*>([^<]+)</title>", re.IGNORECASE)

# Search results often surface sponsored links, social profiles, news,
# directory pages, or investor portfolios first. Skip those when picking
# a candidate URL — we want the company's own site whenever possible.
_SKIP_DOMAINS = (
    "linkedin.com", "facebook.com", "twitter.com", "x.com",
    "crunchbase.com", "bloomberg.com", "pitchbook.com", "instagram.com",
    "wikipedia.org", "youtube.com", "indeed.com", "glassdoor.com",
    "mojeek.com", "ycombinator.com", "techcrunch.com",
    # Aggregators / directories where the company name appears coincidentally.
    "needhelppayingbills.com", "healthgrades.com", "yellowpages.com",
    "bbb.org", "manta.com", "zoominfo.com", "rocketreach.co",
    "owler.com", "tracxn.com", "buzzfile.com", "dnb.com",
)

# URL paths that are almost never the page we want — scoring penalty.
_BAD_PATH_TOKENS = (
    "/terms", "/privacy", "/legal", "/cookie", "/cookies", "/policy",
    "/tos", "/disclaimer", "/accessibility", "/sitemap", "/404",
    "/login", "/signin", "/signup", "/register",
)

# Page titles that signal the URL is a noise sub-page even if it survived
# path filtering. Tested against the lowercased <title>.
_NOISE_TITLE_TOKENS = (
    "privacy policy", "terms of use", "terms of service", "terms and conditions",
    "cookie policy", "cookie notice", "404", "page not found",
    "access denied", "accessibility statement",
)

# Strip legal suffixes and jurisdiction tags so the search query reads
# the way a human would search for the company.
_LEGAL_SUFFIX_RE = re.compile(
    r",?\s*(inc\.?|incorporated|llc|l\.l\.c\.?|ltd\.?|limited|corp\.?|"
    r"corporation|co\.?|company|lp|l\.p\.?|llp|pllc|pc|plc|holdings|"
    r"holding)\s*$",
    re.IGNORECASE,
)
_JURISDICTION_TAG_RE = re.compile(r"\s*/\s*[A-Z]{2,}\s*/\s*$")
_NON_WORD_RE = re.compile(r"[^a-z0-9]+")


@dataclass
class AboutInfo:
    url: str
    description: str


def _strip_suffix(name: str) -> str:
    s = _JURISDICTION_TAG_RE.sub("", name)
    # Apply suffix-strip up to twice to catch e.g. "Foo Holdings, Inc."
    for _ in range(2):
        s = _LEGAL_SUFFIX_RE.sub("", s).rstrip(", ").strip()
    return s


def _distinctive_token(name: str) -> str:
    """First non-generic word of the name, lowercased and de-punctuated."""
    cleaned = _strip_suffix(name).lower()
    parts = [p for p in re.split(r"\W+", cleaned) if p]
    generic = {"the", "a", "an", "health", "healthcare", "medical", "bio",
               "pharma", "therapeutics", "clinical", "care", "labs", "life",
               "diagnostics", "medicine", "biosciences", "company", "group"}
    for p in parts:
        if p not in generic and len(p) > 2:
            return p
    return parts[0] if parts else ""


def _slugify(name: str) -> str:
    return _NON_WORD_RE.sub("", _strip_suffix(name).lower())


def _ranked_candidates(company_name: str, hint: str = "healthcare",
                       timeout: float = 10.0) -> list[tuple[int, str]]:
    """Search Mojeek and return [(score, url)] sorted high-to-low.

    Scoring favours hosts whose name contains the company slug or
    distinctive token, biases toward .com / .health / .io, and penalises
    URLs that point at terms/privacy/policy sub-pages.
    """
    if not company_name:
        return []
    q = f"{_strip_suffix(company_name)} {hint}".strip()
    try:
        resp = requests.get(
            MOJEEK_URL,
            params={"q": q},
            headers={"User-Agent": UA},
            timeout=timeout,
        )
    except requests.RequestException:
        return []
    if resp.status_code != 200 or not resp.text:
        return []

    slug = _slugify(company_name)
    distinctive = _distinctive_token(company_name)

    candidates: list[tuple[int, str]] = []
    seen: set[str] = set()
    for m in _RESULT_HREF.finditer(resp.text):
        url = m.group(1)
        host = urlparse(url).netloc.lower()
        host = host[4:] if host.startswith("www.") else host
        if any(host == d or host.endswith("." + d) for d in _SKIP_DOMAINS):
            continue
        # One result per host; the highest-scoring path wins.
        if host in seen:
            continue
        seen.add(host)

        host_compact = host.replace(".", "").replace("-", "")
        path = urlparse(url).path.lower()
        score = 0
        # Strong signal: company slug appears in the host.
        if slug and len(slug) >= 4 and slug in host_compact:
            score += 10
        # Medium signal: distinctive token is in the host.
        if distinctive and len(distinctive) >= 4 and distinctive in host_compact:
            score += 4
        # Mild preference for .com / .health / .io.
        if host.endswith((".com", ".health", ".io", ".co", ".ai", ".bio")):
            score += 1
        # Penalise paths that obviously aren't the page we want.
        if any(tok in path for tok in _BAD_PATH_TOKENS):
            score -= 5
        # Mild preference for the bare homepage over deep links.
        if path in ("", "/"):
            score += 1
        candidates.append((score, url))
        if len(candidates) >= 10:
            break

    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates


def resolve_url(company_name: str, hint: str = "healthcare",
                timeout: float = 10.0) -> Optional[str]:
    """Best single-URL guess from Mojeek. Kept as a thin wrapper for tests."""
    cands = _ranked_candidates(company_name, hint, timeout=timeout)
    return cands[0][1] if cands else None


def _clean(text: str, max_chars: int = 320) -> str:
    # html.unescape handles every named entity (&amp; &nbsp; &mdash; …) AND
    # numeric entities in either form (&#39; &#039; &#x27;). Beats the
    # hand-rolled replace chain that missed zero-padded numeric entities.
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_chars:
        text = text[: max_chars - 1].rstrip() + "…"
    return text


def _fetch_html(url: str, timeout: float = 10.0) -> Optional[str]:
    try:
        resp = requests.get(url, headers={"User-Agent": UA}, timeout=timeout)
    except requests.RequestException:
        return None
    if resp.status_code != 200:
        return None
    # When a server omits a charset, requests defaults to ISO-8859-1 (per the
    # old HTTP RFC) which mangles UTF-8 multi-byte chars — "Zócalo" becomes
    # "Z\xc3\xb3calo" interpreted as latin-1 → "ZÃ³calo" → "Zócalo"
    # rendered, but our regex sees the raw mojibake. Force a chardet sniff
    # whenever the declared encoding is the default fallback.
    if not resp.encoding or resp.encoding.lower() in ("iso-8859-1", "latin-1"):
        sniffed = resp.apparent_encoding
        if sniffed:
            resp.encoding = sniffed
    if not resp.text:
        return None
    return resp.text


def _extract_desc(html: str) -> Optional[str]:
    """Pull a description from og:description / meta description.

    We deliberately do NOT fall back to <title>. A bare title ("About –
    Hopscotch") looks like content but isn't, and the dashboard's
    heuristic focus label is a better default than a hollow phrase.
    """
    for pat in (_OG_DESC_FWD, _OG_DESC_REV, _META_DESC_FWD, _META_DESC_REV):
        m = pat.search(html)
        if m:
            cleaned = _clean(m.group(1))
            if len(cleaned) >= 30:
                return cleaned
    return None


_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def _compact(s: str) -> str:
    """Lowercase and strip everything except a-z0-9."""
    return _ALNUM_RE.sub("", s.lower())


def _verify_page(html: str, slug: str, host_compact: str) -> bool:
    """Confirm the fetched page actually belongs to the target company.

    Requires the company's full alphanumeric slug to appear somewhere
    distinguishing — host, title, or above-the-fold HTML. A single-word
    distinctive token alone is too easy to match by accident (e.g.
    "centaur" matches the unrelated centaur.ai), so we always insist on
    the full compacted name. Pages whose title is dominated by
    terms/privacy/cookie noise are rejected outright.
    """
    if not html or not slug or len(slug) < 4:
        return False

    title_match = _TITLE.search(html)
    title = title_match.group(1).lower() if title_match else ""
    if title and any(tok in title for tok in _NOISE_TITLE_TOKENS):
        return False

    # Slug match in any of: host, title, or first 6KB of body.
    if slug in host_compact:
        return True
    if title and slug in _compact(title):
        return True
    body_compact = _compact(html[:6000])
    if slug in body_compact:
        return True
    return False


def fetch_about(url: str, timeout: float = 10.0) -> Optional[str]:
    """Fetch the URL and extract a description. No verification — kept for tests."""
    html = _fetch_html(url, timeout=timeout)
    if not html:
        return None
    return _extract_desc(html)


def lookup(company_name: str, hint: str = "healthcare",
           delay: float = 1.5, max_candidates: int = 5) -> Optional[AboutInfo]:
    """Walk top-N candidates, return the first verified description.

    Returns None if no candidate verifies. We deliberately prefer "no
    description" to a wrong one — the dashboard falls back to the
    heuristic focus label, which is at worst boring rather than wrong.
    """
    candidates = _ranked_candidates(company_name, hint)
    if not candidates:
        return None
    slug = _slugify(company_name)
    distinctive = _distinctive_token(company_name)
    # Whole-word check rejects "Plowshares" when we're looking for "Plowshare".
    distinctive_re = (
        re.compile(r"\b" + re.escape(distinctive) + r"\b", re.IGNORECASE)
        if distinctive and len(distinctive) >= 4 else None
    )

    for _, url in candidates[:max_candidates]:
        host = urlparse(url).netloc.lower()
        host = host[4:] if host.startswith("www.") else host
        host_compact = _compact(host)

        time.sleep(delay)
        html = _fetch_html(url)
        if not html:
            continue
        if not _verify_page(html, slug, host_compact):
            continue
        desc = _extract_desc(html)
        if not desc:
            continue
        # Final guard: the description text must mention the company by its
        # distinctive token as a whole word. Filters out generic content
        # pages where the slug appears only as part of another word.
        if distinctive_re and not distinctive_re.search(desc):
            continue
        return AboutInfo(url=url, description=desc)
    return None
