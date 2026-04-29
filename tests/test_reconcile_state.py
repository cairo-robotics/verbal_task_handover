"""
Unit tests for src/pipelines/model_alignment/reconcile_state.py

Run with:
    pytest tests/test_reconcile_state.py -v
"""

import pytest

from src.core.representations.pydantic_schema import (
    Argument,
    KnowledgeGraph,
    Location,
    LocationFact,
    RelationFact,
    RelationPredicate,
)
from src.pipelines.model_alignment.reconcile_state import reconcile_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _named(value: str) -> Argument:
    return Argument(type="named", value=value)


def _needs_potion(subject: str, target: str | None = None) -> RelationFact:
    return RelationFact(
        predicate=RelationPredicate.NEEDS_POTION,
        subject=_named(subject),
        target=_named(target) if target else None,
    )


def _potion_delivered(subject: str, obj: str | None = None, target: str | None = None) -> RelationFact:
    return RelationFact(
        predicate=RelationPredicate.POTION_DELIVERED,
        subject=_named(subject),
        object=_named(obj) if obj else None,
        target=_named(target) if target else None,
    )


def _has_message_for(subject: str, target: str) -> RelationFact:
    return RelationFact(
        predicate=RelationPredicate.HAS_MESSAGE_FOR,
        subject=_named(subject),
        target=_named(target),
    )


def _message_delivered(subject: str, target: str) -> RelationFact:
    return RelationFact(
        predicate=RelationPredicate.MESSAGE_DELIVERED,
        subject=_named(subject),
        target=_named(target),
    )


def _has_item(subject: str, item: str) -> RelationFact:
    return RelationFact(
        predicate=RelationPredicate.HAS_ITEM,
        subject=_named(subject),
        object=_named(item),
    )


def _predicates(graph: KnowledgeGraph) -> list[RelationPredicate]:
    return [f.predicate for f in graph.facts if isinstance(f, RelationFact)]


# ---------------------------------------------------------------------------
# Tests — needs vs deliveries
# ---------------------------------------------------------------------------

def test_unsatisfied_need_is_retained():
    """NEEDS_POTION with no matching delivery → fact stays in the graph."""
    need = _needs_potion("lily", target="player")
    graph = KnowledgeGraph(facts=[need])

    result = reconcile_state(graph)

    assert len(result.facts) == 1
    assert result.facts[0].predicate == RelationPredicate.NEEDS_POTION  # type: ignore[union-attr]


def test_satisfied_potion_need_is_retained():
    """NEEDS_POTION + matching POTION_DELIVERED → need is NOW RETAINED per user request."""
    need = _needs_potion("lily", target="player")
    delivery = _potion_delivered("lily", target="player")
    graph = KnowledgeGraph(facts=[need, delivery])

    result = reconcile_state(graph)

    preds = _predicates(result)
    assert RelationPredicate.NEEDS_POTION in preds
    assert RelationPredicate.POTION_DELIVERED in preds


def test_unmatched_potion_delivery_does_not_remove_different_need():
    """Delivery for one subject must not remove a need for a different subject."""
    need = _needs_potion("lily", target="player")
    delivery = _potion_delivered("rose", target="player")  # different subject
    graph = KnowledgeGraph(facts=[need, delivery])

    result = reconcile_state(graph)

    preds = _predicates(result)
    assert RelationPredicate.NEEDS_POTION in preds


def test_satisfied_message_need_is_removed():
    """HAS_MESSAGE_FOR + matching MESSAGE_DELIVERED → need removed."""
    need = _has_message_for("npc1", "player")
    delivery = _message_delivered("npc1", "player")
    graph = KnowledgeGraph(facts=[need, delivery])

    result = reconcile_state(graph)

    preds = _predicates(result)
    assert RelationPredicate.HAS_MESSAGE_FOR not in preds
    assert RelationPredicate.MESSAGE_DELIVERED in preds


def test_satisfied_request_reponse_need_is_removed():
    """Verify that even if input uses 'request' or 'response', it reconciles via HAS_MESSAGE_FOR."""
    # (Since DSL parser now maps response -> HAS_MESSAGE_FOR, we just test the predicate here)
    need = _has_message_for("npc2", "player")
    delivery = _message_delivered("npc2", "player")
    graph = KnowledgeGraph(facts=[need, delivery])

    result = reconcile_state(graph)

    preds = _predicates(result)
    assert RelationPredicate.HAS_MESSAGE_FOR not in preds
    assert RelationPredicate.HAS_MESSAGE_FOR not in preds
    assert RelationPredicate.MESSAGE_DELIVERED in preds


def test_message_need_resolved_with_existential_target():
    """HAS_MESSAGE_FOR with existential target + MESSAGE_DELIVERED with named target → need removed."""
    need = RelationFact(
        predicate=RelationPredicate.HAS_MESSAGE_FOR,
        subject=_named("eliza"),
        target=Argument(type="existential"),
    )
    delivery = _message_delivered("eliza", "lily")
    graph = KnowledgeGraph(facts=[need, delivery])

    result = reconcile_state(graph)

    preds = _predicates(result)
    assert RelationPredicate.HAS_MESSAGE_FOR not in preds
    assert RelationPredicate.MESSAGE_DELIVERED in preds


# ---------------------------------------------------------------------------
# Tests — HAS_ITEM vs POTION_DELIVERED
# ---------------------------------------------------------------------------

def test_has_item_consumed_when_potion_delivered():
    """HAS_ITEM for a delivered item is removed from the graph."""
    item_fact = _has_item("player", "gold potion")
    delivery = _potion_delivered("player", obj="gold potion", target="lily")
    graph = KnowledgeGraph(facts=[item_fact, delivery])

    result = reconcile_state(graph)

    preds = _predicates(result)
    assert RelationPredicate.HAS_ITEM not in preds
    assert RelationPredicate.POTION_DELIVERED in preds


def test_has_item_retained_when_not_delivered():
    """HAS_ITEM for an item that was NOT delivered stays in the graph."""
    item_fact = _has_item("player", "red potion")
    delivery = _potion_delivered("player", obj="gold potion", target="lily")
    graph = KnowledgeGraph(facts=[item_fact, delivery])

    result = reconcile_state(graph)

    preds = _predicates(result)
    assert RelationPredicate.HAS_ITEM in preds


# ---------------------------------------------------------------------------
# Tests — non-RelationFact pass-through
# ---------------------------------------------------------------------------

def test_non_relation_facts_pass_through():
    """LocationFact entries in the graph are untouched by reconciliation."""
    loc_fact = LocationFact(
        entity=_named("lily"),
        location=Location(type="room", room="room 1"),
    )
    need = _needs_potion("lily", target="player")
    delivery = _potion_delivered("lily", target="player")
    graph = KnowledgeGraph(facts=[loc_fact, need, delivery])

    result = reconcile_state(graph)

    loc_facts = [f for f in result.facts if isinstance(f, LocationFact)]
    assert len(loc_facts) == 1
    assert loc_facts[0].entity.value == "lily"
    # Potion need is retained now
    assert any(f.predicate == RelationPredicate.NEEDS_POTION for f in result.facts if isinstance(f, RelationFact))


# ---------------------------------------------------------------------------
# Tests — immutability
# ---------------------------------------------------------------------------

def test_original_graph_not_mutated():
    """reconcile_state must not modify the original graph object."""
    need = _needs_potion("lily", target="player")
    delivery = _potion_delivered("lily", target="player")
    graph = KnowledgeGraph(facts=[need, delivery])
    original_count = len(graph.facts)

    reconcile_state(graph)

    assert len(graph.facts) == original_count


# ---------------------------------------------------------------------------
# Tests — empty graph
# ---------------------------------------------------------------------------

def test_empty_graph_returns_empty_graph():
    graph = KnowledgeGraph(facts=[])
    result = reconcile_state(graph)
    assert result.facts == []
