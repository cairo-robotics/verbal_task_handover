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
    Also strips leading articles, maps word numbers to digits, and cleans room references.
    """
    if not s:
        return ""
    s = s.strip().lower()
    
    # 1. Strip leading articles (a, an, the)
    s = re.sub(r"^(?:a|an|the)\b\s*", "", s)
    
    # 2. Map word numbers to digits
    num_map = {
        "zero": "0",
        "one": "1",
        "two": "2",
        "three": "3",
        "four": "4",
        "five": "5"
    }
    for word, digit in num_map.items():
        s = re.sub(rf"\b{word}\b", digit, s)
        
    # 3. Strip word "room" when accompanied by storage/lounge/hallway
    for word in ["storage", "lounge", "hallway"]:
        if word in s and "room" in s:
            s = s.replace("room", "")
            
    return "".join(ch for ch in s if ch not in " _-\t\n\r\f\v")

def canonicalize_entity_name(s: str) -> str:
    """
    Normalizes and then applies alias lookup to get a consistent surface form
    if one exists in the alias table.
    """
    norm = normalize_entity_name(s)
    return _ALIAS_TABLE.get(norm, s)

def standardize_room_name(s: str) -> str:
    """
    Standardizes a room name to match the canonical telemetry format.
    E.g., "storage room 1" -> "storage 1", "hallway room 3" -> "hallway 3", "Room 5" -> "room 5"
    """
    if not s:
        return ""
    s = s.strip().lower()
    
    # 1. Strip leading articles (a, an, the)
    s = re.sub(r"^(?:a|an|the)\b\s*", "", s)
    
    # 2. Map word numbers to digits
    num_map = {
        "zero": "0",
        "one": "1",
        "two": "2",
        "three": "3",
        "four": "4",
        "five": "5"
    }
    for word, digit in num_map.items():
        s = re.sub(rf"\b{word}\b", digit, s)
        
    # 3. Strip word "room" when accompanied by storage/lounge/hallway
    for word in ["storage", "lounge", "hallway"]:
        if word in s and "room" in s:
            s = s.replace("room", "")
            
    # Clean up double/multiple spaces
    s = re.sub(r"\s+", " ", s).strip()
    
    # Map back to a clean canonical room pattern if it matches "roomX", "hallwayX", etc.
    m = re.match(r"^(room|hallway|lounge|storage)\s*(\d+)$", s)
    if m:
        return f"{m.group(1)} {m.group(2)}"
        
    return s

