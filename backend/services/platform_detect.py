from __future__ import annotations

import re
from urllib.parse import urlparse

_PLATFORM_HOSTS = {
    "linkedin.com": "linkedin",
    "www.linkedin.com": "linkedin",
    "upwork.com": "upwork",
    "www.upwork.com": "upwork",
    "fiverr.com": "fiverr",
    "www.fiverr.com": "fiverr",
    "facebook.com": "facebook",
    "www.facebook.com": "facebook",
    "fb.com": "facebook",
    "instagram.com": "instagram",
    "www.instagram.com": "instagram",
    "maps.google.com": "google_maps",
    "www.google.com": "google_maps",
    "goo.gl": "google_maps",
    "chat.whatsapp.com": "whatsapp",
    "wa.me": "whatsapp",
    "api.whatsapp.com": "whatsapp",
}


def detect_platform(url: str | None, fallback: str = "other") -> str:
    if fallback and fallback not in ("all", "other", "paste"):
        # honor explicit single-platform choice
        if fallback != "all":
            return fallback
    if not url:
        return "other" if fallback in ("all", "paste", "") else fallback
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        return "other"
    if host.startswith("www."):
        host_key = host
    else:
        host_key = host
    if host_key in _PLATFORM_HOSTS:
        return _PLATFORM_HOSTS[host_key]
    # suffix match
    for domain, name in _PLATFORM_HOSTS.items():
        if host.endswith(domain):
            return name
    if "google." in host and "/maps" in (url or ""):
        return "google_maps"
    return "other"


def resolve_item_platform(selected: str, url: str | None) -> str:
    selected = (selected or "other").lower()
    if selected == "all":
        return detect_platform(url, fallback="other")
    return selected
