#!/usr/bin/env python3
"""
Convert a NarrativeView JSON file into a FactExtraction (state_ontology) JSON.

This is intended to create deterministic "ground truth" fact sets derived from
the NarrativeView outputs of src/model_alignment/craft_narrative_view.py.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Iterable, Optional

import state_ontology

import dotenv
dotenv.load_dotenv()

def _repo_root() -> Path:
    # .../src/extraction_metrics/narrative_view_to_fact_extraction.py -> repo root
    return Path(__file__).resolve().parents[3]


def _ensure_model_alignment_importable() -> None:
    model_alignment_dir = _repo_root() / "src" / "model_alignment"
    if str(model_alignment_dir) not in sys.path:
        sys.path.insert(0, str(model_alignment_dir))


def _normalize_value(value: str) -> str:
    """
    Ontology-style normalization:
    - lowercase
    - spaces -> underscores
    - collapse non [a-z0-9_] to underscores
    - collapse repeated underscores
    - strip underscores
    """
    s = value.strip().lower().replace(" ", "_")
    s = re.sub(r"[^a-z0-9_]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s


_DELIVERED_RE = re.compile(r"^was\s+delivered:\s+(?P<object>.+?)\s+by\s+(?P<actor>.+)$")
_REQUEST_RE = re.compile(r"^request[_\s]+from[_\s]+room[_\s]*(?P<roomnum>[0-9]+)$")
_RESPONSE_RE = re.compile(r"^response[_\s]+from[_\s]+(?P<npc>[a-z0-9_]+)$")


def _is_potion_like(s: str) -> bool:
    return "potion" in _normalize_value(s)


def _iter_rooms(narrative_view: Any) -> Iterable[Any]:
    # NarrativeView.world_state.rooms is always present per the model.
    return getattr(getattr(narrative_view, "world_state", None), "rooms", []) or []


def _build_room_to_patient(narrative_view: Any) -> dict[str, str]:
    """
    Build room name -> patient npc name.

    Heuristic: pick the first character in the room with a potion requirement;
    fallback to the first character if none have requirements.
    """
    out: dict[str, str] = {}
    for room in _iter_rooms(narrative_view):
        room_name = _normalize_value(getattr(room, "name", ""))
        chars = getattr(room, "characters_present", []) or []
        if not room_name or not chars:
            continue

        chosen = None
        for ch in chars:
            reqs = getattr(ch, "requirements", []) or []
            if any(_is_potion_like(r) for r in reqs):
                chosen = ch
                break
        if chosen is None:
            chosen = chars[0]

        out[room_name] = _normalize_value(getattr(chosen, "name", ""))
    return out


def _maybe_fact_key(fact: state_ontology.Fact) -> tuple:
    data = fact.model_dump()
    t = data.pop("type", None)
    return (t, tuple(sorted(data.items())))


def narrative_view_to_fact_extraction(narrative_view: Any) -> state_ontology.FactExtraction:
    facts: list[state_ontology.Fact] = []

    player_room_raw = getattr(getattr(narrative_view, "player_state", None), "current_location", "") or ""
    player_room = _normalize_value(player_room_raw) if player_room_raw else ""
    if player_room:
        facts.append(state_ontology.PlayerLocation(type="PlayerLocation", room=player_room))

    room_to_patient = _build_room_to_patient(narrative_view)

    # Locations and needs
    for room in _iter_rooms(narrative_view):
        room_name = _normalize_value(getattr(room, "name", ""))
        if not room_name:
            continue

        # NpcLocation facts from explicit placement in the NarrativeView.
        for ch in getattr(room, "characters_present", []) or []:
            npc = _normalize_value(getattr(ch, "name", ""))
            if npc:
                facts.append(state_ontology.NpcLocation(type="NpcLocation", npc=npc, room=room_name))

            # PatientNeedsPotion facts from requirements
            for req in getattr(ch, "requirements", []) or []:
                if not _is_potion_like(req):
                    continue
                potion_color = _normalize_value(req)
                patient = npc
                if patient and potion_color:
                    facts.append(
                        state_ontology.PatientNeedsPotion(
                            type="PatientNeedsPotion",
                            patient=patient,
                            potion_color=potion_color,
                        )
                    )

            # Delivered-message subset inferred from interaction_history strings
            for line in getattr(ch, "interaction_history", []) or []:
                m = _DELIVERED_RE.match(line.strip())
                if not m:
                    continue
                obj_norm = _normalize_value(m.group("object"))

                # request from room N -> MessageDelivered(sender_patient, target_npc)
                rm = _REQUEST_RE.match(obj_norm)
                if rm:
                    roomnum = rm.group("roomnum")
                    sender_room = _normalize_value(f"room{roomnum}")
                    sender_patient = room_to_patient.get(sender_room)
                    target_npc = npc
                    if sender_patient and target_npc:
                        facts.append(
                            state_ontology.MessageDelivered(
                                type="MessageDelivered",
                                sender_patient=sender_patient,
                                target_npc=target_npc,
                            )
                        )
                    continue

                # response from <npc> -> ResponseDelivered(sender_npc, target_patient)
                resp = _RESPONSE_RE.match(obj_norm)
                if resp:
                    sender_npc = _normalize_value(resp.group("npc"))
                    target_patient = npc
                    if sender_npc and target_patient:
                        facts.append(
                            state_ontology.ResponseDelivered(
                                type="ResponseDelivered",
                                sender_npc=sender_npc,
                                target_patient=target_patient,
                            )
                        )
                    continue

        # PotionLocation facts for room items
        for item in getattr(room, "items_present", []) or []:
            if not _is_potion_like(item):
                continue
            facts.append(
                state_ontology.PotionLocation(
                    type="PotionLocation",
                    potion_color=_normalize_value(item),
                    room=room_name,
                )
            )

        # PlayerHasItem heuristic for "held" potion:
        # NarrativeView intentionally omits potions from inventory; v1 heuristic is
        # to treat any potion present in the player's current room as held.
        if player_room and room_name == player_room:
            for item in getattr(room, "items_present", []) or []:
                if not _is_potion_like(item):
                    continue
                facts.append(
                    state_ontology.PlayerHasItem(
                        type="PlayerHasItem",
                        item=_normalize_value(item),
                    )
                )

    # Deduplicate while preserving order
    seen: set[tuple] = set()
    deduped: list[state_ontology.Fact] = []
    for f in facts:
        k = _maybe_fact_key(f)
        if k in seen:
            continue
        seen.add(k)
        deduped.append(f)

    return state_ontology.FactExtraction(facts=deduped)


def _load_narrative_view(path: str) -> Any:
    _ensure_model_alignment_importable()
    from craft_narrative_view import NarrativeView  # type: ignore

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return NarrativeView.model_validate(data)


def _smoke_test() -> None:
    _ensure_model_alignment_importable()
    from craft_narrative_view import (  # type: ignore
        NarrativeView,
        PlayerState,
        WorldState,
        RoomView,
        CharacterView,
        RoomConnection,
        ConflictSummary,
    )

    nv = NarrativeView(
        player_state=PlayerState(inventory=[], current_location="room2"),
        world_state=WorldState(
            rooms=[
                RoomView(
                    name="room2",
                    connected_to=[RoomConnection(direction="north_of", room="hallway_1")],
                    characters_present=[
                        CharacterView(
                            name="oliver",
                            interaction_history=[
                                "was delivered: response from John by player"
                            ],
                            requirements=["blue_potion"],
                        )
                    ],
                    items_present=["blue_potion"],
                ),
                RoomView(
                    name="room1",
                    connected_to=[],
                    characters_present=[
                        CharacterView(
                            name="lily",
                            interaction_history=[
                                "was delivered: request from room 1 by player"
                            ],
                            requirements=["gold_potion"],
                        )
                    ],
                    items_present=[],
                ),
            ]
        ),
        unresolved_conflicts=[ConflictSummary(description="x", involved_entities=["a"])],
    )

    fx = narrative_view_to_fact_extraction(nv)
    dumped = fx.model_dump()
    assert "facts" in dumped and isinstance(dumped["facts"], list)
    types = {f["type"] for f in dumped["facts"]}
    assert "PlayerLocation" in types
    assert "NpcLocation" in types
    assert "PatientNeedsPotion" in types
    assert "PotionLocation" in types
    assert "PlayerHasItem" in types
    assert "ResponseDelivered" in types


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert a NarrativeView JSON file into a FactExtraction JSON."
    )
    parser.add_argument(
        "input_file",
        nargs="?",
        help="Filename (or path under processed_output/) to NarrativeView JSON file",
        default="ari_test_narrative_view_output.json",
    )
    parser.add_argument(
        "--smoke-test", # run via PYTHONPATH=src/model_alignment python3 src/extraction_metrics/narrative_view_to_fact_extraction.py --smoke-test
        action="store_true",
        help="Run a minimal internal self-check and exit.",
    )
    args = parser.parse_args()

    if args.smoke_test:
        _smoke_test()
        return

    data_dir = os.environ.get("DATA_DIR")
    if not data_dir:
        print("Error: DATA_DIR must be set.", file=sys.stderr)
        sys.exit(1)

    input_path = os.path.join(data_dir, "processed_output", args.input_file + "_narrative_view_output.json")

    nv = _load_narrative_view(input_path)
    fx = narrative_view_to_fact_extraction(nv)

    output_filename = os.path.join(data_dir, "analysis", args.input_file + "_fact_extraction_output.json")
    with open(output_filename, "w") as f:
        json.dump(fx.model_dump(), f, indent=2)
    print(f"Fact extraction output written to {output_filename}")

if __name__ == "__main__":
    main()

