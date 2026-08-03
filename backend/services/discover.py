"""
Deep public platform discovery — multi-pass search for higher accuracy.

Takes longer on purpose (multi-query + paced requests + AI ranking).
Does NOT log into private groups.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass

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

# Prefer platforms that usually have public hiring signal first
PRIORITY_WHEN_ALL = [
    "upwork",
    "linkedin",
    "fiverr",
    "facebook",
    "other",
    "google_maps",
    "instagram",
    "whatsapp",
]


@dataclass
class DiscoveredItem:
    text: str
    url: str | None
    source: str
    title: str | None = None


def _client() -> OpenAI:
    return OpenAI(api_key=settings.openai_api_key, timeout=60.0)


def build_search_queries(intent: str, platform: str) -> list[tuple[str, str]]:
    """Multiple queries per platform for deeper coverage."""
    intent = re.sub(r"\s+", " ", intent.strip())
    if platform == "all":
        platforms = PRIORITY_WHEN_ALL[:5]
    else:
        platforms = [platform]

    n = max(2, settings.discover_queries_per_platform)
    crafted: dict[str, list[str]] = {}
    try:
        prompt = f"""Create {n} different high-precision Google-style search queries per platform
to find GENUINE public hiring / lead posts (not spam, not courses).

USER INTENT: {intent}
PLATFORMS: {", ".join(platforms)}

Rules:
- Vary wording across the {n} queries (synonyms, role titles, "looking for", "need", "hire").
- Use site: filters when useful.
- Prefer recent hiring language.
- Avoid queries that mainly find blogs/courses/ads.

Return JSON:
{{
  "linkedin": ["q1", "q2", "q3"],
  ...
}}
Only include requested platforms. No markdown."""
        resp = _client().chat.completions.create(
            model=settings.openai_model,
            temperature=0.2,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": "You craft precise search queries for genuine hiring leads.",
                },
                {"role": "user", "content": prompt},
            ],
        )
        raw = json.loads(resp.choices[0].message.content or "{}")
        for key, val in raw.items():
            if isinstance(val, list):
                crafted[key] = [str(x).strip() for x in val if str(x).strip()]
            elif isinstance(val, str) and val.strip():
                crafted[key] = [val.strip()]
    except Exception:
        crafted = {}

    out: list[tuple[str, str]] = []
    for p in platforms:
        queries = crafted.get(p) or []
        if not queries:
            site = PLATFORM_SITE.get(p, "")
            queries = [
                f'{site} {intent} (hiring OR "looking for" OR need)'.strip(),
                f'{site} {intent} (freelance OR contractor OR "web developer")'.strip(),
                f'{site} "{intent}" (hire OR hiring)'.strip(),
            ]
        for q in queries[:n]:
            out.append((p, re.sub(r"\s+", " ", q).strip()))
    return out


def _search_brave(query: str, max_results: int) -> list[dict]:
    key = (settings.brave_api_key or "").strip()
    if not key:
        return []
    headers = {"Accept": "application/json", "X-Subscription-Token": key}
    with httpx.Client(timeout=35.0) as client:
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
    with httpx.Client(timeout=35.0) as client:
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
    url = "https://html.duckduckgo.com/html/"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
    }
    try:
        with httpx.Client(timeout=35.0, follow_redirects=True, headers=headers) as client:
            r = client.post(url, data={"q": query})
            r.raise_for_status()
            html = r.text
    except Exception:
        return []

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
        m = re.search(r"uddg=([^&]+)", href)
        if m:
            from urllib.parse import unquote

            return unquote(m.group(1))
        if href.startswith("//"):
            return "https:" + href
        return href

    results = []
    for i, (href, title) in enumerate(titles_links[:max_results]):
        body = clean(snippets[i]) if i < len(snippets) else ""
        results.append({"title": clean(title), "href": unwrap(href), "body": body})
    return results


def search_web(query: str, max_results: int | None = None) -> list[dict]:
    n = max_results or 8
    for fn in (_search_brave, _search_serpapi, _search_ddgs, _search_duckduckgo_html):
        try:
            found = fn(query, n)
            if found:
                return found[:n]
        except Exception:
            continue
    return []


_SPAM_HINTS = re.compile(
    r"\b(course|tutorial|udemy|guaranteed income|make money fast|followers|crypto pump)\b",
    re.I,
)


def _looks_weak(text: str) -> bool:
    if len(text) < 40:
        return True
    if _SPAM_HINTS.search(text):
        return True
    return False


def discover_items(intent: str, platform: str = "all") -> list[DiscoveredItem]:
    """
    Deep multi-pass discovery.
    Paces searches so a full run typically lands in the ~3–5 minute window
    together with AI classification.
    """
    queries = build_search_queries(intent, platform)
    per_query = max(5, settings.discover_max_results // max(1, len(queries)))
    pause = max(3.0, float(settings.discover_pause_seconds))

    seen_urls: set[str] = set()
    seen_text: set[str] = set()
    items: list[DiscoveredItem] = []

    for idx, (p, query) in enumerate(queries):
        rows = search_web(query, per_query)
        for row in rows:
            url = (row.get("href") or "").strip()
            title = (row.get("title") or "").strip()
            body = (row.get("body") or "").strip()
            text = f"{title}\n{body}".strip()
            key = re.sub(r"\s+", " ", text.lower())[:180]
            if url and url in seen_urls:
                continue
            if key in seen_text:
                continue
            if _looks_weak(text):
                continue
            if url:
                seen_urls.add(url)
            seen_text.add(key)
            items.append(
                DiscoveredItem(text=text, url=url or None, source=p, title=title or None)
            )

        # Pace between query batches (skip after last)
        if idx < len(queries) - 1:
            time.sleep(pause)

    return items


def rerank_matches_with_ai(intent: str, matches: list[dict]) -> list[dict]:
    """Second-pass genuineness ranking for final accuracy."""
    if not matches:
        return matches
    payload = [
        {
            "i": i,
            "text": (m.get("raw_text") or "")[:500],
            "score": m.get("genuine_score", 0),
            "source": m.get("source"),
        }
        for i, m in enumerate(matches[:25])
    ]
    try:
        resp = _client().chat.completions.create(
            model=settings.openai_model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You re-rank lead candidates for genuineness vs user intent. "
                        "Prefer specific hiring asks over generic pages/directories."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"INTENT: {intent}\nCANDIDATES:\n{json.dumps(payload)}\n"
                        'Return JSON {"order":[best_index_first...], '
                        '"scores":{"0":0-100,...}}'
                    ),
                },
            ],
        )
        data = json.loads(resp.choices[0].message.content or "{}")
        scores = data.get("scores") or {}
        for i, m in enumerate(matches[:25]):
            if str(i) in scores:
                try:
                    m["genuine_score"] = float(scores[str(i)])
                except (TypeError, ValueError):
                    pass
        order = data.get("order")
        if isinstance(order, list) and order:
            ordered = []
            used = set()
            for idx in order:
                try:
                    idx_i = int(idx)
                except (TypeError, ValueError):
                    continue
                if 0 <= idx_i < len(matches) and idx_i not in used:
                    ordered.append(matches[idx_i])
                    used.add(idx_i)
            for i, m in enumerate(matches):
                if i not in used:
                    ordered.append(m)
            return ordered
    except Exception:
        pass
    matches.sort(
        key=lambda r: (r.get("genuine_score", 0), r.get("confidence", 0)),
        reverse=True,
    )
    return matches
