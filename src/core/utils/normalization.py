import re

# Maps variants that appear in reporter text → canonical telemetry form.
# Keys are already *normalised* (lowercase, no underscores/hyphens/spaces).
# Values are the canonical surface form used in the telemetry graph.
_ALIAS_TABLE: dict[str, str] = {
    # Potion colour variants
    "goldpotion": "gold potion",
    "redpotion": "red potion",
    "bluepotion": "blue potion",
    "greenpotion": "green potion",
    "purplepotion": "purple potion",
    "silverpotion": "silver potion",
    "whitepotion": "white potion",
    "blackpotion": "black potion",
}

def normalize_entity_name(s: str) -> str:
    """
    Robustly normalizes an entity or location name for comparison.
    Lowercase, stripped, and removes all spaces, underscores, and hyphens.
    """
    if not s:
        return ""
    s = s.strip().lower()
    return "".join(ch for ch in s if ch not in " _-\t\n\r\f\v")

def canonicalize_entity_name(s: str) -> str:
    """
    Normalizes and then applies alias lookup to get a consistent surface form
    if one exists in the alias table.
    """
    norm = normalize_entity_name(s)
    return _ALIAS_TABLE.get(norm, s)
