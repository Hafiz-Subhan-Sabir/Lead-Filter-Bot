"""
Public platform discovery — finds posts/listings via web search.

Does NOT log into private LinkedIn/WhatsApp/Facebook groups.
Searches the public web for pages on those platforms matching the intent.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from urllib.parse import quote_plus

import httpx
from openai import OpenAI

from config import settings

PLATFORM_SITE = {
    "linkedin": "site:linkedin.com",
    "upwork": "site:upwork.com",
    "fiverr": "site:fiverr.com",
    "facebook": "site:facebook.com",
    "instagram": "site:instagram.com",
    "google_maps": "",
    "whatsapp": "",
    "other": "",
}

ALL_PLATFORMS = [
    "linkedin",
    "upwork",
    "fiverr",
    "facebook",
    "instagram",
    "google_maps",
    "whatsapp",
    "other",
]


@dataclass
class DiscoveredItem:
    text: str
    url: str | None
    source: str
    title: str | None = None


def _client() -> OpenAI:
    return OpenAI(api_key=settings.openai_api_key, timeout=45.0)


def build_search_queries(intent: str, platform: str) -> list[tuple[str, str]]:
    intent = re.sub(r"\s+", " ", intent.strip())
    platforms = ALL_PLATFORMS if platform == "all" else [platform]

    crafted: dict[str, str] = {}
    try:
        prompt = f"""Create one short Google-style search query per platform to find REAL public hiring/lead posts.
USER INTENT: {intent}
PLATFORMS: {", ".join(platforms)}

Rules:
- Include intent keywords.
- Use site: filters when helpful (linkedin.com, upwork.com, etc.).
- For google_maps focus on businesses needing websites.
- For whatsapp focus on public pages mentioning hiring in groups/communities.
Return JSON object: platform -> query string. No markdown."""
        resp = _client().chat.completions.create(
            model=settings.openai_model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": "You write precise public web search queries for genuine hiring leads.",
                },
                {"role": "user", "content": prompt},
            ],
        )
        crafted = json.loads(resp.choices[0].message.content or "{}")
    except Exception:
        crafted = {}

    out: list[tuple[str, str]] = []
    for p in platforms:
        custom = crafted.get(p) if isinstance(crafted.get(p), str) else None
        if custom and custom.strip():
            q = custom.strip()
        else:
            site = PLATFORM_SITE.get(p, "")
            if p == "google_maps":
                q = f'{intent} ("need a website" OR "no website" OR "looking for web developer") business'
            elif p == "whatsapp":
                q = f'{intent} (whatsapp OR telegram) (hiring OR "looking for" OR freelance)'
            else:
                q = f'{site} {intent} (hiring OR "looking for" OR need OR freelance)'.strip()
        out.append((p, re.sub(r"\s+", " ", q).strip()))
    return out


def _search_brave(query: str, max_results: int) -> list[dict]:
    key = (settings.brave_api_key or "").strip()
    if not key:
        return []
    headers = {"Accept": "application/json", "X-Subscription-Token": key}
    with httpx.Client(timeout=30.0) as client:
        r = client.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": query, "count": max_results},
            headers=headers,
        )
        r.raise_for_status()
        data = r.json()
    return [
        {
            "title": item.get("title") or "",
            "href": item.get("url") or "",
            "body": item.get("description") or "",
        }
        for item in ((data.get("web") or {}).get("results") or [])
    ]


def _search_serpapi(query: str, max_results: int) -> list[dict]:
    key = (settings.serpapi_key or "").strip()
    if not key:
        return []
    with httpx.Client(timeout=30.0) as client:
        r = client.get(
            "https://serpapi.com/search.json",
            params={"engine": "google", "q": query, "api_key": key, "num": max_results},
        )
        r.raise_for_status()
        data = r.json()
    return [
        {
            "title": item.get("title") or "",
            "href": item.get("link") or "",
            "body": item.get("snippet") or "",
        }
        for item in (data.get("organic_results") or [])
    ]


def _search_ddgs(query: str, max_results: int) -> list[dict]:
    try:
        try:
            from ddgs import DDGS  # type: ignore
        except ImportError:
            from duckduckgo_search import DDGS  # type: ignore
    except ImportError:
        return []

    results = []
    try:
        with DDGS() as ddgs:
            for item in ddgs.text(query, max_results=max_results):
                results.append(
                    {
                        "title": item.get("title") or "",
                        "href": item.get("href") or item.get("link") or "",
                        "body": item.get("body") or item.get("snippet") or "",
                    }
                )
    except Exception:
        return []
    return results


def _search_duckduckgo_html(query: str, max_results: int) -> list[dict]:
    """Fallback HTML scrape of DuckDuckGo html endpoint."""
    url = "https://html.duckduckgo.com/html/"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
    }
    try:
        with httpx.Client(timeout=30.0, follow_redirects=True, headers=headers) as client:
            r = client.post(url, data={"q": query})
            r.raise_for_status()
            html = r.text
    except Exception:
        return []

    # Parse result blocks: uddg redirect links + snippets
    results = []
    # links
    link_re = re.compile(
        r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
        re.I | re.S,
    )
    snip_re = re.compile(r'class="result__snippet"[^>]*>(.*?)</(?:a|td|div)', re.I | re.S)

    titles_links = link_re.findall(html)
    snippets = snip_re.findall(html)

    def clean(s: str) -> str:
        s = re.sub(r"<[^>]+>", " ", s)
        return re.sub(r"\s+", " ", s).strip()

    def unwrap(href: str) -> str:
        # DuckDuckGo often wraps as //duckduckgo.com/l/?uddg=ENCODED
        m = re.search(r"uddg=([^&]+)", href)
        if m:
            from urllib.parse import unquote

            return unquote(m.group(1))
        if href.startswith("//"):
            return "https:" + href
        return href

    for i, (href, title) in enumerate(titles_links[:max_results]):
        body = clean(snippets[i]) if i < len(snippets) else ""
        results.append(
            {
                "title": clean(title),
                "href": unwrap(href),
                "body": body,
            }
        )
    return results


def search_web(query: str, max_results: int | None = None) -> list[dict]:
    n = max_results or settings.discover_max_results
    for fn in (_search_brave, _search_serpapi, _search_ddgs, _search_duckduckgo_html):
        try:
            found = fn(query, n)
            if found:
                return found[:n]
        except Exception:
            continue
    return []


def discover_items(intent: str, platform: str = "all") -> list[DiscoveredItem]:
    queries = build_search_queries(intent, platform)
    # For "all", fewer per platform to keep total reasonable
    per_platform = max(
        3,
        settings.discover_max_results // max(1, min(len(queries), 4)),
    )
    # Limit concurrent platforms when all selected for speed
    if platform == "all":
        queries = queries[:5]

    seen_urls: set[str] = set()
    items: list[DiscoveredItem] = []

    for p, query in queries:
        for row in search_web(query, per_platform):
            url = (row.get("href") or "").strip()
            title = (row.get("title") or "").strip()
            body = (row.get("body") or "").strip()
            if url and url in seen_urls:
                continue
            if url:
                seen_urls.add(url)
            text = f"{title}\n{body}".strip()
            if len(text) < 24:
                continue
            items.append(
                DiscoveredItem(
                    text=text,
                    url=url or None,
                    source=p,
                    title=title or None,
                )
            )

    return items
