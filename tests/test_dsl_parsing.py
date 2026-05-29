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
