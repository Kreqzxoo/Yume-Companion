from typing import Optional


def normalize_tags(raw) -> list:
    if isinstance(raw, str):
        parts = raw.split(",")
    elif isinstance(raw, (list, tuple)):
        parts = []
        for item in raw:
            if isinstance(item, str):
                parts.extend(item.split(","))
            else:
                parts.append(str(item))
    else:
        return []

    seen = set()
    out = []
    for p in parts:
        t = p.strip().lower()
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return out[:20]  # sane cap


def message_count(char_data: dict) -> int:
    total = 0
    for chat in (char_data or {}).get("chats", {}).values():
        total += len(chat.get("chat_content", {}) or {})
    return total


def _parse_iso(value) -> str:
    s = str(value or "")
    return s if s else "0000-00-00T00:00:00"


def sort_character_entries(entries, mode: str = "name_asc"):
    mode = (mode or "name_asc").strip()

    if mode == "recent":
        def key(item):
            name, data = item
            return (_parse_iso(data.get("last_opened")), name.lower())
        ordered = sorted(entries, key=key, reverse=True)
        return [n for n, _ in ordered]

    if mode == "messages":
        def key(item):
            name, data = item
            return (-message_count(data), name.lower())
        ordered = sorted(entries, key=key)
        return [n for n, _ in ordered]

    if mode == "name_desc":
        return [n for n, _ in sorted(entries, key=lambda x: x[0].lower(), reverse=True)]

    return [n for n, _ in sorted(entries, key=lambda x: x[0].lower())]


def matches_hub_filter(name: str, data: dict, query: str = "",
                       tag: Optional[str] = None,
                       search_hits_grouped: bool = True) -> bool:
    q = (query or "").strip().lower()
    tags = data.get("tags") or []

    if q:
        hit = q in name.lower()
        if not hit and tags:
            hit = any(q in t.lower() for t in tags)
        if not hit:
            return False

    if tag and tag not in ("all", None):
        if q and search_hits_grouped:
            pass
        if tag not in [t.lower() for t in tags]:
            return False

    return True
