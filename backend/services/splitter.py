def split_into_items(text: str) -> list[str]:
    """Split pasted text into items by blank lines."""
    chunks = [c.strip() for c in text.split("\n\n")]
    return [c for c in chunks if c]
