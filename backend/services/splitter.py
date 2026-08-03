from __future__ import annotations

import re
from dataclasses import dataclass

_URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)


@dataclass
class ParsedItem:
    text: str
    url: str | None = None


def split_into_items(text: str) -> list[ParsedItem]:
    """
    Split pasted text by blank lines.
    If a chunk ends with (or contains) a URL, attach it and remove it from text.
    """
    chunks = [c.strip() for c in text.split("\n\n")]
    items: list[ParsedItem] = []

    for chunk in chunks:
        if not chunk:
            continue

        urls = _URL_RE.findall(chunk)
        url = urls[-1] if urls else None

        clean = chunk
        if url:
            clean = _URL_RE.sub("", chunk).strip()
            # tidy leftover blank lines
            clean = re.sub(r"\n{3,}", "\n\n", clean).strip()

        if not clean and url:
            # URL-only block — skip
            continue
        if not clean:
            continue

        items.append(ParsedItem(text=clean, url=url))

    return items
