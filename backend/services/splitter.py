from __future__ import annotations

import re
from dataclasses import dataclass

_URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
_TIME_PREFIX_RE = re.compile(
    r"^(?:time|posted|ago)?\s*[\[(]?\s*(\d+(?:\.\d+)?)\s*(h|hr|hrs|hour|hours|d|day|days)\s*[\])]?\s*[:\-]?\s*",
    re.I,
)


@dataclass
class ParsedItem:
    text: str
    url: str | None = None
    hours_ago_hint: float | None = None


def _parse_time_prefix(text: str) -> tuple[str, float | None]:
    m = _TIME_PREFIX_RE.match(text.strip())
    if not m:
        return text, None
    value = float(m.group(1))
    unit = m.group(2).lower()
    hours = value * 24 if unit.startswith("d") else value
    rest = text.strip()[m.end() :].strip()
    return rest, hours


def split_into_items(text: str) -> list[ParsedItem]:
    """
    Split by blank lines.
    Optional URL on any line.
    Optional time prefix: "6h: ..." or "[12h] ..." or "2 days: ..."
    """
    chunks = [c.strip() for c in text.split("\n\n")]
    items: list[ParsedItem] = []

    for chunk in chunks:
        if not chunk:
            continue

        urls = _URL_RE.findall(chunk)
        url = urls[-1] if urls else None
        clean = _URL_RE.sub("", chunk).strip() if url else chunk
        clean = re.sub(r"\n{3,}", "\n\n", clean).strip()

        hours_hint = None
        lines = clean.split("\n")
        if lines:
            first, hours_hint = _parse_time_prefix(lines[0])
            if hours_hint is not None:
                lines[0] = first
                clean = "\n".join(lines).strip()

        if not clean:
            continue

        items.append(ParsedItem(text=clean, url=url, hours_ago_hint=hours_hint))

    return items
