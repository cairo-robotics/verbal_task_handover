import re
import os
import sys
import json
from typing import Optional, List, Tuple

try:
    from src.core.representations.pydantic_schema import (
        KnowledgeGraph, RelationFact, LocationFact, SpatialFact, ConnectionFact,
        Argument, Location, Direction, RelationPredicate, SpatialRelationType,
    )
except ImportError:
    # pyrefly: ignore [missing-import]
    from pydantic_schema import (
        KnowledgeGraph, RelationFact, LocationFact, SpatialFact, ConnectionFact,
        Argument, Location, Direction, RelationPredicate, SpatialRelationType,
    )

import dotenv

dotenv.load_dotenv()

# for reference when implementing the parser
# DSL_CONVERSION_PROMPT = """
# OUTPUT FORMAT RULES:

# - Use ONLY the exact templates shown below
# - Use ONLY lowercase letters
# - Do NOT include punctuation
# - Do NOT include extra words
# - Do NOT paraphrase templates
# - Do NOT infer unstated facts
# - Do NOT include duplicate facts

# ---
# ENTITY TYPES include npcs, locations, and items (potions, requests or messages, responses).
# - npcs: <npc name>
# - location: <location name>
# - item: <potion_color> potion

# If the entity agent is unspecified (e.g., "someone", "a patient", "a potion"), use <unknown>:
# - npcs: someone
# - items: a potion
# - locations: somewhere

# FACT TEMPLATES:

# # Potions
# <npc> needs a <potion_color or unknown> potion
# <potion_color or unknown> potion delivered to <npc>

# # Messaging (includes requests, messages, and responses)
# <npc> has a message for <npc>
# message delivered from <npc> to <npc>

# # Locations and spatial relationships
# player is in <room>
# <entity> is in <room>
# <entity> is to the <direction>
# <entity> is <direction> of <entity>
# <location> is connected to <location>

# # Inventory
# player has <item>


# If the agent is unspecified (e.g., "someone", "a patient"), use:

# someone needs <potion_color> potion
# someone has a message/response for someone

# If a location constraint is given, include it:

# someone to the <direction> needs <potion_color> potion

# Do not infer specific agents, locations, or objects.

# ---

# EXAMPLE 1:

# INPUT:
# "Northwest Room (Room 1) needs the gold potion
# Southwest Room (Room 2) needs the blue potion
# Northeast Room (Room 3) needs the red potion
# Southeast Room (Room 4) needs the green potion

# There is a fifth room that I did not get around to (NPC named GUY), there is also someone there who wants a potion, I did not get around to it.

# The NPCs won't give you medals just for giving them a potion, you will also have to actually deliver messages for them. Make sure you explore all rooms, and names of people in the rooms. Usually helps to make exploration a side taks when fetching items or delivering messages."

# OUTPUT:
# room 1 is to the northwest
# room 1 needs a gold potion
# room 2 is to the southwest
# room 2 needs a blue potion
# room 3 is to the northeast
# room 3 needs a red potion
# room 4 is to the southeast
# room 4 needs a green potion
# guy is in room 5
# room 5 needs a potion

# ---
# EXAMPLE 2:

# INPUT:
# "You have to assist with delivering potions and messages from certain people. I have done some of it. These are the things you need to finish for me and there are some more that I do not remember.
# 1. Lily (in West and then North) requires another Gold potion.
# 2. Some people require red and green potions in the East wing.
# 3. I think a person wanted an orange potion in the South wing.
# 4. Steve has a message for John.
# 5. I also saw teal and pale blue potion, along with dark purple in the South wing. 
# 6. There were some other potions in the north and then east wing. 
# 7. There were people with messages on the West wing that I could not attend to."

# OUTPUT:
# lily is to the west-then-north
# someone to the east needs a red potion
# someone to the east needs a green potion
# someone to the south needs an orange potion
# steve has a message for john
# teal potion is to the south
# pale blue potion is to the south
# dark purple potion is to the south
# some potion is to the north-then-east
# someone to the west has a message for someone

# ---
# EXAMPLE 3:

# INPUT:
# "**Handoff Report**

# **Outstanding Patient Needs:**
# 1. **Room 1 (Lily)** - Requires **gold potion**.
# 2. **Room 2 (Oliver)** - Requires **blue potion**.
# 3. **Room 3 (Nick)** - Requires **red potion**.
# 4. **Room 4 (Marie)** - Requires **green potion**.

# **Pending Requests and Responses:**
# - None.

# **Relevant Inventory Items:**
# - None.

# **NPC Locations:**
# - **Lily** is in **Room 1**.
# - **Oliver** is in **Room 2**.
# - **Nick** is in **Room 3**.
# - **Marie** is in **Room 4**.
# - **Storage 2** (where **blue potion** and **green potion** are located) is accessible from **Hallway 5**.
# - **Storage 1** (where **red potion** is located) is accessible from **Hallway 3**.

# **Current Location:**
# - The player is currently in **Hallway 1**. 

# **Next Steps:**
# - Retrieve the required potions from the respective storage areas and deliver them to the patients in their rooms."

# OUTPUT:
# room 1 needs a gold potion
# room 2 needs a blue potion
# room 3 needs a red potion
# room 4 needs a green potion
# lily is in room 1
# oliver is in room 2
# nick is in room 3
# marie is in room 4
# blue potion is in storage 2
# green potion is in storage 2
# storage 2 is connected to hallway 5
# red potion is in storage 1
# storage 1 is connected to hallway 3
# player is in hallway 1
# ---

# Now extract facts from the following text:

# {INPUT_TEXT}
# """


# ---- Direction helpers ----

DIRECTION_MAP = {
    "north": Direction.NORTH,
    "south": Direction.SOUTH,
    "east": Direction.EAST,
    "west": Direction.WEST,
    "northeast": Direction.NORTHEAST,
    "northwest": Direction.NORTHWEST,
    "southeast": Direction.SOUTHEAST,
    "southwest": Direction.SOUTHWEST,
}

# Regex fragment matching any single direction keyword
_DIR_RE = r"(?:north(?:east|west)?|south(?:east|west)?|east|west)"


def _parse_direction(text: str) -> Optional[Direction]:
    return DIRECTION_MAP.get(text.strip().lower())


def _is_location(text: str) -> bool:
    text = text.lower().strip()
    return any(
        text.startswith(prefix)
        for prefix in ["room", "hallway", "storage", "lounge"]
    )


_DIRECTION_INVERSES = {
    Direction.NORTH: Direction.SOUTH,
    Direction.SOUTH: Direction.NORTH,
    Direction.EAST: Direction.WEST,
    Direction.WEST: Direction.EAST,
    Direction.NORTHEAST: Direction.SOUTHWEST,
    Direction.SOUTHWEST: Direction.NORTHEAST,
    Direction.NORTHWEST: Direction.SOUTHEAST,
    Direction.SOUTHEAST: Direction.NORTHWEST,
}


def _invert_direction(direction: Direction) -> Direction:
    return _DIRECTION_INVERSES[direction]


def _parse_directional_location(dir_text: str) -> Optional[Location]:
    """Parse direction text into a Location.

    Handles single directions ("north") and compound paths/sets
    ("west-then-north", "north-and-east").
    """
    dir_text = dir_text.strip().lower()
    if "-then-" in dir_text:
        parts = [p.strip() for p in dir_text.split("-then-")]
        dirs = [_parse_direction(p) for p in parts]
        if all(d is not None for d in dirs):
            return Location(type="directional", directions=dirs, mode="path")
    elif "-and-" in dir_text:
        parts = [p.strip() for p in dir_text.split("-and-")]
        dirs = [_parse_direction(p) for p in parts]
        if all(d is not None for d in dirs):
            return Location(type="directional", directions=dirs, mode="set")
    else:
        d = _parse_direction(dir_text)
        if d is not None:
            return Location(type="directional", directions=[d])
    return None


# ---- Argument helpers ----

def _parse_subject(text: str) -> Argument:
    """Parse a subject, handling 'someone', 'someone to the <dir>', and named entities."""
    text = text.strip()
    m = re.match(r'^someone to the (.+)$', text, re.IGNORECASE)
    if m:
        loc = _parse_directional_location(m.group(1).strip())
        return Argument(type="existential", location=loc)
    if text.lower() == "someone":
        return Argument(type="existential")
    return Argument(type="named", value=text)


def _parse_entity(text: str) -> Argument:
    """Parse a plain entity reference (no location constraint expected)."""
    text = text.strip()
    if text.lower() == "someone":
        return Argument(type="existential")
    return Argument(type="named", value=text)


def _parse_potion_arg(text: str) -> Argument:
    """Parse a potion description like 'a gold potion', 'an orange potion', 'a potion'.

    Strips any leading article and trailing ' potion'.  Returns existential if
    no colour is specified.
    """
    text = text.strip().lower()
    # Strip leading article
    text = re.sub(r'^an? +', '', text)
    if text == "potion":
        return Argument(type="existential")
    if text.endswith(" potion"):
        color = text[: -len(" potion")].strip()
        return Argument(type="named", value=color + " potion")
    # Bare colour word(s) without explicit "potion" suffix (shouldn't occur in
    # well-formed DSL, but handle gracefully)
    return Argument(type="named", value=text + " potion")


def _parse_room_location(text: str) -> Location:
    return Location(type="room", room=text.strip())


# ---- Line parser ----

def _parse_line(line: str):
    """Parse a single DSL line into a Fact.

    Returns None for blank lines and comment lines (starting with '#').
    Raises ValueError if the line is non-empty but cannot be matched.
    """
    line = line.strip()
    if not line or line.startswith("#"):
        return None

    # ------------------------------------------------------------------
    # Relation facts
    # ------------------------------------------------------------------

    # "<subject> needs [a|an] [<color>] potion"
    m = re.match(r'^(.+?) needs (.+)$', line, re.IGNORECASE)
    if m:
        rest = m.group(2).strip()
        if re.match(r'^(?:an? +)?(?:.+ +)?potion$', rest, re.IGNORECASE):
            subject = _parse_subject(m.group(1))
            obj = _parse_potion_arg(rest)
            is_partial = subject.type == "existential" or obj.type == "existential"
            return RelationFact(
                predicate=RelationPredicate.NEEDS_POTION,
                subject=subject,
                object=obj,
                is_partial=is_partial,
                provenance=line,
            )

    # "[<color>] potion delivered to <npc>"
    m = re.match(r'^(.+) potion delivered to (.+)$', line, re.IGNORECASE)
    if m:
        potion_text = m.group(1).strip()
        npc = _parse_entity(m.group(2))
        obj = _parse_potion_arg(potion_text + " potion")
        is_partial = npc.type == "existential" or obj.type == "existential"
        return RelationFact(
            predicate=RelationPredicate.POTION_DELIVERED,
            subject=npc,
            object=obj,
            is_partial=is_partial,
            provenance=line,
        )

    # "<subject> has a [message|response] for <target>"
    m = re.match(r'^(.+?) has a (?:message|response) for (.+)$', line, re.IGNORECASE)
    if m:
        subject = _parse_subject(m.group(1))
        target = _parse_subject(m.group(2))
        return RelationFact(
            predicate=RelationPredicate.HAS_MESSAGE_FOR,
            subject=subject,
            target=target,
            is_partial=subject.type == "existential" or target.type == "existential",
            provenance=line,
        )

    # "[message|response] delivered from <sender> to <recipient>"
    m = re.match(r'^(?:message|response) delivered from (.+?) to (.+)$', line, re.IGNORECASE)
    if m:
        sender = _parse_entity(m.group(1))
        recipient = _parse_entity(m.group(2))
        return RelationFact(
            predicate=RelationPredicate.MESSAGE_DELIVERED,
            subject=sender,
            target=recipient,
            is_partial=sender.type == "existential" or recipient.type == "existential",
            provenance=line,
        )

    # "player has <item>"
    m = re.match(r'^player has (.+)$', line, re.IGNORECASE)
    if m:
        item = _parse_entity(m.group(1))
        return RelationFact(
            predicate=RelationPredicate.HAS_ITEM,
            subject=Argument(type="named", value="player"),
            object=item,
            is_partial=item.type == "existential",
            provenance=line,
        )

    # ------------------------------------------------------------------
    # Location / spatial facts
    # ------------------------------------------------------------------

    # "<entity> is in <room>"  (also covers "player is in <room>")
    m = re.match(r'^(.+?) is in (.+)$', line, re.IGNORECASE)
    if m:
        entity = _parse_entity(m.group(1))
        location = _parse_room_location(m.group(2))
        return LocationFact(
            entity=entity,
            location=location,
            is_partial=entity.type == "existential",
            provenance=line,
        )

    # "<entity> is to the <direction>"
    # Single direction → SpatialFact(absolute); compound path → LocationFact
    m = re.match(r'^(.+?) is to the (.+)$', line, re.IGNORECASE)
    if m:
        entity = _parse_entity(m.group(1))
        dir_text = m.group(2).strip().lower()
        if "-then-" in dir_text or "-and-" in dir_text:
            loc = _parse_directional_location(dir_text)
            if loc is None:
                raise ValueError(
                    f"Cannot parse compound direction {dir_text!r}"
                )
            return LocationFact(
                entity=entity,
                location=loc,
                is_partial=entity.type == "existential",
                provenance=line,
            )
        d = _parse_direction(dir_text)
        if d is None:
            raise ValueError(f"Unknown direction {dir_text!r}")
        return SpatialFact(
            type=SpatialRelationType.ABSOLUTE,
            subject=entity,
            direction=d,
            is_partial=entity.type == "existential",
            provenance=line,
        )

    # "<entity> is <direction> of <reference>"
    m = re.match(r"^(.+?) is (" + _DIR_RE + r") of (.+)$", line, re.IGNORECASE)
    if m:
        entity_text = m.group(1).strip()
        direction_text = m.group(2).strip()
        reference_text = m.group(3).strip()

        entity = _parse_entity(entity_text)
        direction = _parse_direction(direction_text)
        reference = _parse_entity(reference_text)

        if _is_location(entity_text) and _is_location(reference_text):
            loc_a = _parse_room_location(reference_text)
            loc_b = _parse_room_location(entity_text)
            dir_enum = direction

            # Normalize: sort by room name
            if loc_a.room > loc_b.room:
                loc_a, loc_b = loc_b, loc_a
                if dir_enum:
                    dir_enum = _invert_direction(dir_enum)

            return ConnectionFact(
                location_a=loc_a,
                location_b=loc_b,
                direction=dir_enum,
                is_partial=False,
                provenance=line,
            )

        return SpatialFact(
            type=SpatialRelationType.RELATIVE,
            subject=entity,
            direction=direction,
            reference=reference,
            is_partial=entity.type == "existential" or reference.type == "existential",
            provenance=line,
        )

    # "<location> is connected to <location>"
    m = re.match(r"^(.+?) is connected to (.+)$", line, re.IGNORECASE)
    if m:
        loc_a = _parse_room_location(m.group(1))
        loc_b = _parse_room_location(m.group(2))

        # Normalize: sort by room name
        if loc_a.room > loc_b.room:
            loc_a, loc_b = loc_b, loc_a

        return ConnectionFact(
            location_a=loc_a,
            location_b=loc_b,
            is_partial=False,
            provenance=line,
        )

    # raise ValueError(f"Line could not be matched to any DSL template: {line!r}")
    print(f"Line could not be matched to any DSL template: {line!r}")
    return None


# ---- Public API ----

def dsl_to_graph(text_filename: str, output_filename: str) -> None:
    """Parse a DSL text file into a KnowledgeGraph and write it as JSON."""
    with open(text_filename, "r") as f:
        lines = f.readlines()

    facts = []
    for lineno, raw_line in enumerate(lines, start=1):
        try:
            fact = _parse_line(raw_line)
        except ValueError as exc:
            raise ValueError(f"Parse error on line {lineno}: {exc}") from exc
        if fact is not None:
            facts.append(fact)

    kg = KnowledgeGraph(facts=facts)

    os.makedirs(os.path.dirname(output_filename), exist_ok=True)
    with open(output_filename, "w") as f:
        json.dump(kg.model_dump(), f, indent=2)


if __name__ == "__main__":
    data_dir = os.environ.get("DATA_DIR")
    if not data_dir:
        raise SystemExit("DATA_DIR environment variable is not set")
    if len(sys.argv) < 2:
        raise SystemExit("usage: dsl_to_graph.py <dsl_relative_path>")
        
    text_filename = os.path.join(data_dir, sys.argv[1])
    
    # Standardize output naming: [pid]_dsl_to_kg.json under processed_output/kg
    stem = os.path.basename(sys.argv[1]).split(".")[0]
    if stem.endswith("_dsl"):
        stem = stem[:-4]
    output_filename = os.path.join(data_dir, "processed_output", "kg", f"{stem}_dsl_to_kg.json")
    dsl_to_graph(text_filename, output_filename)
