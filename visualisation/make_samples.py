"""
Generates sample JSON files that match the KnowledgeGraph pydantic schema.
Run once to create test data: python make_samples.py
"""
import json, uuid, pathlib

out = pathlib.Path("samples")
out.mkdir(exist_ok=True)

def uid(): return str(uuid.uuid4())

# ── telemetry_graph.json ─────────────────────────────────────────────────────
telemetry = {
    "facts": [
        {
            "id": uid(), "is_partial": False, "provenance": None, "source": "base",
            "entity": {"type": "named", "value": "lily", "location": None},
            "location": {"type": "room", "room": "room_b", "directions": None, "mode": None}
        },
        {
            "id": uid(), "is_partial": False, "provenance": None, "source": "base",
            "entity": {"type": "named", "value": "red_key", "location": None},
            "location": {"type": "room", "room": "room_c", "directions": None, "mode": None}
        },
        {
            "id": uid(), "is_partial": False, "provenance": None, "source": "base",
            "entity": {"type": "named", "value": "blue_potion", "location": None},
            "location": {"type": "room", "room": "room_b", "directions": None, "mode": None}
        },
        {
            "id": uid(), "is_partial": False, "provenance": None, "source": "base",
            "predicate": "needs_potion",
            "subject": {"type": "named", "value": "lily", "location": None},
            "object": {"type": "named", "value": "blue_potion", "location": None},
            "target": None
        },
        {
            "id": uid(), "is_partial": False, "provenance": None, "source": "base",
            "predicate": "has_message_for",
            "subject": {"type": "named", "value": "marcus", "location": None},
            "object": None,
            "target": {"type": "named", "value": "player", "location": None}
        },
        {
            "id": uid(), "is_partial": False, "provenance": None, "source": "base",
            "entity": {"type": "named", "value": "marcus", "location": None},
            "location": {"type": "room", "room": "room_a", "directions": None, "mode": None}
        },
        {
            "id": uid(), "is_partial": False, "provenance": None, "source": "base",
            "type": "relative",
            "subject": {"type": "named", "value": "room_c", "location": None},
            "direction": "north",
            "reference": {"type": "named", "value": "room_b", "location": None}
        },
        {
            "id": uid(), "is_partial": False, "provenance": None, "source": "base",
            "location_a": {"type": "room", "room": "room_a", "directions": None, "mode": None},
            "location_b": {"type": "room", "room": "room_b", "directions": None, "mode": None},
            "direction": "east"
        },
    ],
    "conflicts": []
}

# ── user_report_graph.json ───────────────────────────────────────────────────
user_report = {
    "facts": [
        {
            "id": uid(), "is_partial": False,
            "provenance": "lily is somewhere nearby", "source": "new",
            "entity": {"type": "named", "value": "lily", "location": None},
            "location": {"type": "room", "room": "room_b", "directions": None, "mode": None}
        },
        {
            "id": uid(), "is_partial": True,
            "provenance": "I think the key was somewhere to the north", "source": "new",
            "entity": {"type": "named", "value": "red_key", "location": None},
            "location": {"type": "directional", "room": None, "directions": ["north"], "mode": "path"}
        },
        {
            "id": uid(), "is_partial": False,
            "provenance": "picked up the blue potion", "source": "new",
            "entity": {"type": "named", "value": "blue_potion", "location": None},
            "location": {"type": "room", "room": "room_b", "directions": None, "mode": None}
        },
        {
            "id": uid(), "is_partial": False,
            "provenance": "lily needs it", "source": "new",
            "predicate": "needs_potion",
            "subject": {"type": "named", "value": "lily", "location": None},
            "object": {"type": "named", "value": "blue_potion", "location": None},
            "target": None
        },
        {
            "id": uid(), "is_partial": True,
            "provenance": "someone had a message for me I think", "source": "new",
            "predicate": "has_message_for",
            "subject": {"type": "existential", "value": None, "location": None},
            "object": None,
            "target": {"type": "named", "value": "player", "location": None}
        },
    ],
    "conflicts": []
}

# ── merged_graph.json ────────────────────────────────────────────────────────
conflict_id = uid()
merged = {
    "facts": [
        # shared — from telemetry
        {
            "id": uid(), "is_partial": False, "provenance": None, "source": "base",
            "entity": {"type": "named", "value": "lily", "location": None},
            "location": {"type": "room", "room": "room_b", "directions": None, "mode": None}
        },
        {
            "id": uid(), "is_partial": False, "provenance": None, "source": "base",
            "entity": {"type": "named", "value": "blue_potion", "location": None},
            "location": {"type": "room", "room": "room_b", "directions": None, "mode": None}
        },
        {
            "id": uid(), "is_partial": False, "provenance": None, "source": "base",
            "predicate": "needs_potion",
            "subject": {"type": "named", "value": "lily", "location": None},
            "object": {"type": "named", "value": "blue_potion", "location": None},
            "target": None
        },
        {
            "id": uid(), "is_partial": False, "provenance": None, "source": "base",
            "predicate": "has_message_for",
            "subject": {"type": "named", "value": "marcus", "location": None},
            "object": None,
            "target": {"type": "named", "value": "player", "location": None}
        },
        {
            "id": uid(), "is_partial": False, "provenance": None, "source": "base",
            "entity": {"type": "named", "value": "marcus", "location": None},
            "location": {"type": "room", "room": "room_a", "directions": None, "mode": None}
        },
        # telemetry ground truth for conflicted fact
        {
            "id": "fact-redkey-base", "is_partial": False, "provenance": None, "source": "base",
            "entity": {"type": "named", "value": "red_key", "location": None},
            "location": {"type": "room", "room": "room_c", "directions": None, "mode": None}
        },
        # novel from user
        {
            "id": uid(), "is_partial": False, "provenance": "Room B has stuff I didn't check", "source": "new",
            "predicate": "has_item",
            "subject": {"type": "named", "value": "room_b", "location": None},
            "object": {"type": "existential", "value": None, "location": None},
            "target": None
        },
        {
            "id": uid(), "is_partial": False, "provenance": None, "source": "base",
            "type": "relative",
            "subject": {"type": "named", "value": "room_c", "location": None},
            "direction": "north",
            "reference": {"type": "named", "value": "room_b", "location": None}
        },
        {
            "id": uid(), "is_partial": False, "provenance": None, "source": "base",
            "location_a": {"type": "room", "room": "room_a", "directions": None, "mode": None},
            "location_b": {"type": "room", "room": "room_b", "directions": None, "mode": None},
            "direction": "east"
        },
    ],
    "conflicts": [
        {
            "id": uid(),
            "base_fact_id": "fact-redkey-base",
            "new_fact": {
                "id": uid(), "is_partial": True,
                "provenance": "I think the key was somewhere to the north",
                "source": "new",
                "entity": {"type": "named", "value": "red_key", "location": None},
                "location": {"type": "directional", "room": None, "directions": ["north"], "mode": "path"}
            },
            "field_name": "location",
            "base_value": {"type": "room", "room": "room_c"},
            "new_value": {"type": "directional", "directions": ["north"]}
        }
    ]
}

(out / "telemetry_graph.json").write_text(json.dumps(telemetry, indent=2))
(out / "user_report_graph.json").write_text(json.dumps(user_report, indent=2))
(out / "merged_graph.json").write_text(json.dumps(merged, indent=2))

print("Written:", [str(p) for p in sorted(out.iterdir())])
