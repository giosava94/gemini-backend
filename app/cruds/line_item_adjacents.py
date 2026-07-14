def has_duplicate_adjacent_items(items: list[dict]) -> bool:
    """Return True if *items* contains two entries with the same (id, position) pair."""
    seen: set[tuple] = set()
    for adjacent in items:
        key = (adjacent.get("id"), adjacent.get("position"))
        if key in seen:
            return True
        seen.add(key)
    return False


def has_duplicate_adjacent_index_in_items(items: list[dict]) -> bool:
    """Return True if *items* contains two entries sharing the same (position, index) pair."""
    seen: set[tuple] = set()
    for adjacent in items:
        if adjacent.get("index") is None:
            continue
        key = (adjacent.get("position"), adjacent.get("index"))
        if key in seen:
            return True
        seen.add(key)
    return False
