import unittest
from src.core.representations.pydantic_schema import (
    KnowledgeGraph,
    RelationFact,
    LocationFact,
    SpatialFact,
    ConnectionFact,
    Argument,
    Location,
    Direction,
    RelationPredicate,
)
from src.pipelines.model_alignment.craft_narrative_view import craft_narrative_view

class TestCraftNarrativeViewV2(unittest.TestCase):
    def test_basic_transformation(self):
        # Setup a sample KnowledgeGraph
        player_arg = Argument(type="named", value="player")
        lily_arg = Argument(type="named", value="lily")
        potion_arg = Argument(type="named", value="gold potion")
        room1_arg = Argument(type="named", value="room 1")
        room2_arg = Argument(type="named", value="room 2")

        facts = [
            # Player location
            LocationFact(
                entity=player_arg,
                location=Location(type="room", room="room 1")
            ),
            # Lily location
            LocationFact(
                entity=lily_arg,
                location=Location(type="room", room="room 2")
            ),
            # Lily needs a potion
            RelationFact(
                predicate=RelationPredicate.NEEDS_POTION,
                subject=lily_arg,
                object=potion_arg
            ),
            # Player has a message for lily (history)
            RelationFact(
                predicate=RelationPredicate.MESSAGE_DELIVERED,
                subject=player_arg,
                target=lily_arg,
                object=Argument(type="named", value="hello")
            ),
            # Room 1 is connected to Room 2
            ConnectionFact(
                location_a=Location(type="room", room="room 1", directions=[Direction.EAST]),
                location_b=Location(type="room", room="room 2")
            )
        ]
        
        kg = KnowledgeGraph(facts=facts)
        
        # Run the transformation
        narrative_view = craft_narrative_view(kg)
        
        # Verify Player State
        self.assertEqual(narrative_view.player_state.current_location, "room 1")
        
        # Verify World State (Rooms)
        room_names = [room.name for room in narrative_view.world_state.rooms]
        self.assertIn("room 1", room_names)
        self.assertIn("room 2", room_names)
        
        # Verify room 1 connections
        room1 = next(r for r in narrative_view.world_state.rooms if r.name == "room 1")
        self.assertEqual(len(room1.connected_to), 1)
        self.assertEqual(room1.connected_to[0].room, "room 2")
        self.assertEqual(room1.connected_to[0].direction, "east")
        
        # Verify Lily View in room 2
        room2 = next(r for r in narrative_view.world_state.rooms if r.name == "room 2")
        lily_view = next(c for c in room2.characters_present if c.name == "lily")
        self.assertIn("needs gold potion", lily_view.requirements)
        self.assertTrue(any("message" in h for h in lily_view.interaction_history))

    def test_existential_need_in_room_preservation(self):
        # Setup a sample KnowledgeGraph with an existential need constraint
        # e.g., "someone in room 1 needs a gold potion"
        existential_subj = Argument(
            type="existential",
            value=None,
            location=Location(type="room", room="room 1")
        )
        potion_arg = Argument(type="named", value="gold potion")
        
        facts = [
            # The existential need
            RelationFact(
                predicate=RelationPredicate.NEEDS_POTION,
                subject=existential_subj,
                object=potion_arg
            ),
            # Define room 1 as a valid location room in the graph
            LocationFact(
                entity=Argument(type="named", value="player"),
                location=Location(type="room", room="room 1")
            )
        ]
        
        kg = KnowledgeGraph(facts=facts)
        narrative_view = craft_narrative_view(kg)
        
        # Verify that the existential relation is NOT silently dropped
        # and is preserved in unanchored_facts.
        self.assertEqual(len(narrative_view.unanchored_facts), 1)
        self.assertIn("needs_potion", narrative_view.unanchored_facts[0])
        self.assertIn("gold potion", narrative_view.unanchored_facts[0])
        self.assertIn("room 1", narrative_view.unanchored_facts[0])

if __name__ == "__main__":
    unittest.main()
