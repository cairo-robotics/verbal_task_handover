from src.core.transforms.dsl_to_graph import _parse_line
from src.core.representations.pydantic_schema import RelationPredicate

def test_parse_has_received_potion():
    # Named NPC and potion
    fact1 = _parse_line("guy has received a gold potion")
    assert fact1 is not None
    assert fact1.predicate == RelationPredicate.POTION_DELIVERED
    assert fact1.subject.type == "named"
    assert fact1.subject.value == "guy"
    assert fact1.object.type == "named"
    assert fact1.object.value == "gold potion"
    assert fact1.is_partial is False

    # The article and existential NPC
    fact2 = _parse_line("someone has received the blue potion")
    assert fact2 is not None
    assert fact2.predicate == RelationPredicate.POTION_DELIVERED
    assert fact2.subject.type == "existential"
    assert fact2.object.type == "named"
    assert fact2.object.value == "blue potion"
    assert fact2.is_partial is True

    # Bare item/no article
    fact3 = _parse_line("lily has received blue potion")
    assert fact3 is not None
    assert fact3.predicate == RelationPredicate.POTION_DELIVERED
    assert fact3.subject.value == "lily"
    assert fact3.object.value == "blue potion"

def test_parse_delivered_message():
    # Named recipient and sender
    fact1 = _parse_line("guy was delivered a message from marie")
    assert fact1 is not None
    assert fact1.predicate == RelationPredicate.MESSAGE_DELIVERED
    assert fact1.subject.type == "named"
    assert fact1.subject.value == "marie"  # sender is subject
    assert fact1.target.type == "named"
    assert fact1.target.value == "guy"    # recipient is target
    assert fact1.is_partial is False

    # Existential sender
    fact2 = _parse_line("lily was delivered a message from someone")
    assert fact2 is not None
    assert fact2.predicate == RelationPredicate.MESSAGE_DELIVERED
    assert fact2.subject.type == "existential"
    assert fact2.target.type == "named"
    assert fact2.target.value == "lily"
    assert fact2.is_partial is True

def test_parse_relative_directions():
    from src.core.representations.pydantic_schema import ConnectionFact, SpatialFact, SpatialRelationType, Direction

    # 1. ConnectionFact: storage room 1 is to the north of hallway 3
    fact1 = _parse_line("storage room 1 is to the north of hallway 3")
    assert fact1 is not None
    assert isinstance(fact1, ConnectionFact)
    assert fact1.location_a.room == "hallway 3"
    assert fact1.location_b.room == "storage 1"
    assert fact1.direction == Direction.NORTH
    assert fact1.is_partial is False

    # 2. ConnectionFact (without 'to the'): storage room 1 is north of hallway 3
    fact2 = _parse_line("storage room 1 is north of hallway 3")
    assert fact2 is not None
    assert isinstance(fact2, ConnectionFact)
    assert fact2.location_a.room == "hallway 3"
    assert fact2.location_b.room == "storage 1"
    assert fact2.direction == Direction.NORTH
    assert fact2.is_partial is False

    # 3. SpatialFact (relative, named): guy is north of room 5
    fact3 = _parse_line("guy is north of room 5")
    assert fact3 is not None
    assert isinstance(fact3, SpatialFact)
    assert fact3.type == SpatialRelationType.RELATIVE
    assert fact3.subject.type == "named"
    assert fact3.subject.value == "guy"
    assert fact3.direction == Direction.NORTH
    assert fact3.reference.type == "named"
    assert fact3.reference.value == "room 5"
    assert fact3.is_partial is False

    # 4. SpatialFact (relative, existential with 'to the'): someone is to the east of room 4
    fact4 = _parse_line("someone is to the east of room 4")
    assert fact4 is not None
    assert isinstance(fact4, SpatialFact)
    assert fact4.type == SpatialRelationType.RELATIVE
    assert fact4.subject.type == "existential"
    assert fact4.direction == Direction.EAST
    assert fact4.reference.type == "named"
    assert fact4.reference.value == "room 4"
    assert fact4.is_partial is True

def test_parse_directional_rooms():
    from src.core.representations.pydantic_schema import LocationFact, Direction
    
    # 1. "donna is in the north west room"
    fact1 = _parse_line("donna is in the north west room")
    assert fact1 is not None
    assert isinstance(fact1, LocationFact)
    assert fact1.entity.value == "donna"
    assert fact1.location.type == "directional"
    assert fact1.location.directions == [Direction.NORTHWEST]
    
    # 2. "john is in the north room"
    fact2 = _parse_line("john is in the north room")
    assert fact2 is not None
    assert isinstance(fact2, LocationFact)
    assert fact2.entity.value == "john"
    assert fact2.location.type == "directional"
    assert fact2.location.directions == [Direction.NORTH]

    # 3. "lola is in the north east room"
    fact3 = _parse_line("lola is in the north east room")
    assert fact3 is not None
    assert isinstance(fact3, LocationFact)
    assert fact3.entity.value == "lola"
    assert fact3.location.type == "directional"
    assert fact3.location.directions == [Direction.NORTHEAST]

    # 4. "gems are in a room up north-then-east"
    fact4 = _parse_line("gems are in a room up north-then-east")
    assert fact4 is not None
    assert isinstance(fact4, LocationFact)
    assert fact4.entity.value == "gems"
    assert fact4.location.type == "directional"
    assert fact4.location.directions == [Direction.NORTH, Direction.EAST]
    assert fact4.location.mode == "path"

def test_parse_directional_aliases():
    from src.core.representations.pydantic_schema import LocationFact, SpatialFact, ConnectionFact, Direction, SpatialRelationType
    
    # 1. "donna is in the top-left room"
    fact1 = _parse_line("donna is in the top-left room")
    assert fact1 is not None
    assert isinstance(fact1, LocationFact)
    assert fact1.location.directions == [Direction.NORTHWEST]

    # 2. "player is in the bottom room"
    fact2 = _parse_line("player is in the bottom room")
    assert fact2 is not None
    assert isinstance(fact2, LocationFact)
    assert fact2.location.directions == [Direction.SOUTH]

    # 3. "lounge 1 is left of hallway 2"
    fact3 = _parse_line("lounge 1 is left of hallway 2")
    assert fact3 is not None
    assert isinstance(fact3, ConnectionFact)
    assert fact3.direction == Direction.WEST

    # 4. "guy is to the top right of room 5"
    fact4 = _parse_line("guy is to the top right of room 5")
    assert fact4 is not None
    assert isinstance(fact4, SpatialFact)
    assert fact4.type == SpatialRelationType.RELATIVE
    assert fact4.direction == Direction.NORTHEAST

def test_parse_contains_entities():
    from src.core.representations.pydantic_schema import LocationFact
    
    # 1. "storage 1 contains gold and red potions"
    facts1 = _parse_line("storage 1 contains gold and red potions")
    assert facts1 is not None
    assert isinstance(facts1, list)
    assert len(facts1) == 2
    assert all(isinstance(f, LocationFact) for f in facts1)
    assert facts1[0].entity.value == "gold potion"
    assert facts1[0].location.room == "storage 1"
    assert facts1[1].entity.value == "red potion"
    assert facts1[1].location.room == "storage 1"

    # 2. "storage 2 contains orange blue and green potions"
    facts2 = _parse_line("storage 2 contains orange blue and green potions")
    assert facts2 is not None
    assert isinstance(facts2, list)
    assert len(facts2) == 3
    assert facts2[0].entity.value == "orange potion"
    assert facts2[1].entity.value == "blue potion"
    assert facts2[2].entity.value == "green potion"

    # 3. "lounge 3 contains donna and brittany"
    facts3 = _parse_line("lounge 3 contains donna and brittany")
    assert facts3 is not None
    assert isinstance(facts3, list)
    assert len(facts3) == 2
    assert facts3[0].entity.value == "donna"
    assert facts3[1].entity.value == "brittany"


def test_room_name_standardization():
    from src.core.utils.normalization import standardize_room_name
    assert standardize_room_name("storage room 1") == "storage 1"
    assert standardize_room_name("storage room one") == "storage 1"
    assert standardize_room_name("hallway room 5") == "hallway 5"
    assert standardize_room_name("Room 5") == "room 5"
    assert standardize_room_name("storage1") == "storage 1"
    assert standardize_room_name("lounge room three") == "lounge 3"
    
    # Verify parsing actually standardizes locations
    fact1 = _parse_line("player is in storage room 2")
    assert fact1.location.room == "storage 2"
    
    fact2 = _parse_line("storage room 1 is connected to hallway room 3")
    assert fact2.location_a.room == "hallway 3"
    assert fact2.location_b.room == "storage 1"


def test_parse_new_room_subjects_and_the_articles():
    from src.core.representations.pydantic_schema import Location
    
    # 1. "someone in room 1 needs a gold potion"
    fact1 = _parse_line("someone in room 1 needs a gold potion")
    assert fact1 is not None
    assert fact1.predicate == RelationPredicate.NEEDS_POTION
    assert fact1.subject.type == "existential"
    assert isinstance(fact1.subject.location, Location)
    assert fact1.subject.location.type == "room"
    assert fact1.subject.location.room == "room 1"
    assert fact1.object.type == "named"
    assert fact1.object.value == "gold potion"

    # 2. "someone in the room 1 needs a gold potion"
    fact2 = _parse_line("someone in the room 1 needs a gold potion")
    assert fact2 is not None
    assert fact2.subject.location.room == "room 1"

    # 3. "room 1 needs a gold potion"
    fact3 = _parse_line("room 1 needs a gold potion")
    assert fact3 is not None
    assert fact3.predicate == RelationPredicate.NEEDS_POTION
    assert fact3.subject.type == "existential"
    assert fact3.subject.location.type == "room"
    assert fact3.subject.location.room == "room 1"

    # 4. "someone needs the red potion"
    fact4 = _parse_line("someone needs the red potion")
    assert fact4 is not None
    assert fact4.predicate == RelationPredicate.NEEDS_POTION
    assert fact4.object.type == "named"
    assert fact4.object.value == "red potion"


def test_parse_might_need():
    # 1. "nick might need a red potion"
    fact1 = _parse_line("nick might need a red potion")
    assert fact1 is not None
    assert fact1.predicate == RelationPredicate.NEEDS_POTION
    assert fact1.subject.type == "named"
    assert fact1.subject.value == "nick"
    assert fact1.object.type == "named"
    assert fact1.object.value == "red potion"
    assert fact1.is_partial is False

    # 2. "guy might need an orange potion"
    fact2 = _parse_line("guy might need an orange potion")
    assert fact2 is not None
    assert fact2.predicate == RelationPredicate.NEEDS_POTION
    assert fact2.subject.type == "named"
    assert fact2.subject.value == "guy"
    assert fact2.object.type == "named"
    assert fact2.object.value == "orange potion"
    assert fact2.is_partial is False

    # 3. "someone might need a blue potion"
    fact3 = _parse_line("someone might need a blue potion")
    assert fact3 is not None
    assert fact3.predicate == RelationPredicate.NEEDS_POTION
    assert fact3.subject.type == "existential"
    assert fact3.object.type == "named"
    assert fact3.object.value == "blue potion"
    assert fact3.is_partial is True





