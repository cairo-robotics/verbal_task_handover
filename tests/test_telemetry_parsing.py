import pytest
from src.core.transforms.telemetry_to_graph import convert_telemetry_to_kg
from src.core.representations.pydantic_schema import LocationFact

def test_parse_gave_wrong_item_to_npc(tmp_path):
    # Create a temporary telemetry log file
    telemetry_content = (
        "2025-04-22 12:43:20 - room entered: east to room1\n"
        "2025-04-22 12:43:28 - Gave wrong item to NPC: orange_potion nick\n"
    )
    temp_file = tmp_path / "test_telemetry.txt"
    temp_file.write_text(telemetry_content, encoding="utf-8")

    # Run the converter
    kg = convert_telemetry_to_kg(str(temp_file))

    # Look for the location fact of 'nick' in 'room 1'
    location_facts = [
        f for f in kg.facts if isinstance(f, LocationFact) and f.entity.value == "nick"
    ]

    assert len(location_facts) == 1
    fact = location_facts[0]
    assert fact.location.room == "room 1"
    assert fact.provenance == "Gave wrong item to NPC: orange_potion nick"
