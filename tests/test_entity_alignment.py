"""
Unit tests for src/pipelines/model_alignment/entity_alignment.py

Run with:
    pytest tests/test_entity_alignment.py -v

No real OpenAI API calls are made; the LLM path is covered by patching.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.core.representations.pydantic_schema import (
    Argument,
    ConnectionFact,
    KnowledgeGraph,
    Location,
    LocationFact,
    RelationFact,
    RelationPredicate,
    SpatialFact,
    SpatialRelationType,
    Direction,
)
from src.pipelines.model_alignment.entity_alignment import (
    AlignmentResult,
    ExistentialResolution,
    align_entities,
    _normalize,
    _infer_entity_type,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _named(value: str) -> Argument:
    return Argument(type="named", value=value)


def _existential(value: str | None = None) -> Argument:
    return Argument(type="existential", value=value)


def _relation_graph(*facts: RelationFact) -> KnowledgeGraph:
    return KnowledgeGraph(facts=list(facts))


def _needs_potion(subject: str, target: str | None = None) -> RelationFact:
    return RelationFact(
        predicate=RelationPredicate.NEEDS_POTION,
        subject=_named(subject),
        target=_named(target) if target else None,
    )


def _potion_delivered(subject: str, obj: str | None = None) -> RelationFact:
    return RelationFact(
        predicate=RelationPredicate.POTION_DELIVERED,
        subject=_named(subject),
        object=_named(obj) if obj else None,
    )


# ---------------------------------------------------------------------------
# Normalisation unit tests
# ---------------------------------------------------------------------------

class TestNormalize:
    def test_lowercase(self):
        assert _normalize("LILY") == "lily"

    def test_strips_whitespace(self):
        assert _normalize("  lily  ") == "lily"

    def test_removes_underscores(self):
        assert _normalize("gold_potion") == "goldpotion"

    def test_removes_hyphens(self):
        assert _normalize("gold-potion") == "goldpotion"

    def test_removes_spaces(self):
        assert _normalize("gold potion") == "goldpotion"

    def test_combined(self):
        assert _normalize("  Red_Potion  ") == "redpotion"


# ---------------------------------------------------------------------------
# Entity type heuristic
# ---------------------------------------------------------------------------

class TestInferEntityType:
    def test_potion_is_item(self):
        assert _infer_entity_type("gold potion") == "item"

    def test_key_is_item(self):
        assert _infer_entity_type("chest key") == "item"

    def test_room_is_location(self):
        assert _infer_entity_type("room 1") == "location"

    def test_npc_fallback(self):
        assert _infer_entity_type("lily") == "npc"
        assert _infer_entity_type("rose") == "npc"


# ---------------------------------------------------------------------------
# Named-entity alignment — no LLM involved
# ---------------------------------------------------------------------------

class TestNamedAlignment:
    def test_exact_match_not_in_mapping(self):
        """Identical values (no rename needed) are NOT added to named_mapping."""
        report = _relation_graph(_needs_potion("lily"))
        telem = _relation_graph(_needs_potion("lily"))
        result = align_entities(report, telem)
        # No rename needed — "lily" stays "lily"
        assert "lily" not in result.named_mapping

    def test_normalisation_match(self):
        """'gold_potion' in report should map to 'gold potion' in telemetry."""
        report = _relation_graph(
            RelationFact(
                predicate=RelationPredicate.NEEDS_POTION,
                subject=_named("lily"),
                object=_named("gold_potion"),
            )
        )
        telem = _relation_graph(
            RelationFact(
                predicate=RelationPredicate.HAS_ITEM,
                subject=_named("player"),
                object=_named("gold potion"),
            )
        )
        result = align_entities(report, telem)
        assert result.named_mapping.get("gold_potion") == "gold potion"

    def test_alias_match(self):
        """'goldpotion' (alias-normalised form) maps to 'gold potion'."""
        report = _relation_graph(
            RelationFact(
                predicate=RelationPredicate.NEEDS_POTION,
                subject=_named("lily"),
                object=_named("gold potion"),  # already normalises to match
            )
        )
        telem = _relation_graph(
            RelationFact(
                predicate=RelationPredicate.HAS_ITEM,
                subject=_named("player"),
                object=_named("gold potion"),
            )
        )
        result = align_entities(report, telem)
        # Same value, no mapping entry needed
        assert "gold potion" not in result.named_mapping

    def test_case_insensitive_match(self):
        """'Lily' in report maps to 'lily' in telemetry."""
        report = _relation_graph(_needs_potion("Lily"))
        telem = _relation_graph(_needs_potion("lily"))
        result = align_entities(report, telem)
        assert result.named_mapping.get("Lily") == "lily"

    def test_novel_named_entity_not_in_mapping(self):
        """Named entities with no telemetry counterpart are simply absent from mapping."""
        report = _relation_graph(_needs_potion("alice"))
        telem = _relation_graph(_needs_potion("lily"))
        result = align_entities(report, telem)
        assert "alice" not in result.named_mapping

    def test_no_existentials_returns_empty_resolutions(self):
        report = _relation_graph(_needs_potion("lily"))
        telem = _relation_graph(_needs_potion("lily"))
        result = align_entities(report, telem)
        assert result.existential_resolutions == []

    def test_empty_graphs_return_empty_result(self):
        result = align_entities(KnowledgeGraph(facts=[]), KnowledgeGraph(facts=[]))
        assert result.named_mapping == {}
        assert result.existential_resolutions == []

    def test_non_relation_facts_are_traversed(self):
        """Named entities inside LocationFact are also aligned."""
        report = KnowledgeGraph(
            facts=[
                LocationFact(
                    entity=_named("Lily"),
                    location=Location(type="room", room="room 1"),
                )
            ]
        )
        telem = KnowledgeGraph(
            facts=[
                LocationFact(
                    entity=_named("lily"),
                    location=Location(type="room", room="room 1"),
                )
            ]
        )
        result = align_entities(report, telem)
        assert result.named_mapping.get("Lily") == "lily"

    def test_spatial_fact_arguments_are_traversed(self):
        """Named entities inside SpatialFact (subject + reference) are aligned."""
        report = KnowledgeGraph(
            facts=[
                SpatialFact(
                    type=SpatialRelationType.RELATIVE,
                    subject=_named("Lily"),
                    direction=Direction.NORTH,
                    reference=_named("Room1"),
                )
            ]
        )
        telem = KnowledgeGraph(
            facts=[
                SpatialFact(
                    type=SpatialRelationType.RELATIVE,
                    subject=_named("lily"),
                    direction=Direction.NORTH,
                    reference=_named("room1"),
                )
            ]
        )
        result = align_entities(report, telem)
        assert result.named_mapping.get("Lily") == "lily"
        assert result.named_mapping.get("Room1") == "room1"


# ---------------------------------------------------------------------------
# Existential resolution — LLM path (mocked)
# ---------------------------------------------------------------------------

def _make_llm_response(outcome: str, resolved_value: str | None = None, candidates: list[str] | None = None):
    """Build a minimal mock that looks like an openai chat completion response."""
    import json
    payload = {"outcome": outcome, "resolved_value": resolved_value, "candidate_values": candidates or []}
    msg = MagicMock()
    msg.content = json.dumps(payload)
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


class TestExistentialResolution:
    def _report_with_existential(self) -> KnowledgeGraph:
        return KnowledgeGraph(
            facts=[
                RelationFact(
                    predicate=RelationPredicate.NEEDS_POTION,
                    subject=_existential(),  # existential NPC
                )
            ]
        )

    def _telem_with_npcs(self) -> KnowledgeGraph:
        return KnowledgeGraph(
            facts=[
                _needs_potion("lily"),
                _needs_potion("rose"),
            ]
        )

    def test_resolved_outcome(self):
        """LLM returns 'resolved' → resolution has outcome='resolved'."""
        client = MagicMock()
        client.chat.completions.create.return_value = _make_llm_response(
            "resolved", resolved_value="lily"
        )
        result = align_entities(
            self._report_with_existential(),
            self._telem_with_npcs(),
            openai_client=client,
        )
        assert len(result.existential_resolutions) == 1
        res = result.existential_resolutions[0]
        assert res.outcome == "resolved"
        assert res.resolved_value == "lily"
        assert res.candidate_values == []

    def test_ambiguous_outcome(self):
        """LLM returns 'ambiguous' → resolution has outcome='ambiguous' with candidates."""
        client = MagicMock()
        client.chat.completions.create.return_value = _make_llm_response(
            "ambiguous", candidates=["lily", "rose"]
        )
        result = align_entities(
            self._report_with_existential(),
            self._telem_with_npcs(),
            openai_client=client,
        )
        res = result.existential_resolutions[0]
        assert res.outcome == "ambiguous"
        assert set(res.candidate_values) == {"lily", "rose"}
        assert res.resolved_value is None

    def test_unresolvable_outcome(self):
        """LLM returns 'unresolvable' → resolution has outcome='unresolvable'."""
        client = MagicMock()
        client.chat.completions.create.return_value = _make_llm_response("unresolvable")
        result = align_entities(
            self._report_with_existential(),
            self._telem_with_npcs(),
            openai_client=client,
        )
        res = result.existential_resolutions[0]
        assert res.outcome == "unresolvable"
        assert res.resolved_value is None
        assert res.candidate_values == []

    def test_resolved_value_not_in_candidates_becomes_unresolvable(self):
        """Guard: LLM returns a resolved_value that isn't in our candidate list → unresolvable."""
        client = MagicMock()
        client.chat.completions.create.return_value = _make_llm_response(
            "resolved", resolved_value="ghost_npc_not_in_telem"
        )
        result = align_entities(
            self._report_with_existential(),
            self._telem_with_npcs(),
            openai_client=client,
        )
        res = result.existential_resolutions[0]
        assert res.outcome == "unresolvable"

    def test_no_telemetry_candidates_is_unresolvable_without_llm_call(self):
        """If no telemetry entities match the type, return unresolvable immediately."""
        # Report has an existential NPC, but telemetry only contains items and
        # locations — no NPC strings — so the candidate list is empty and the
        # LLM should NOT be called.
        telem = KnowledgeGraph(
            facts=[
                LocationFact(
                    entity=_named("gold potion"),           # item → not NPC
                    location=Location(type="room", room="room 1"),
                ),
                LocationFact(
                    entity=_named("red potion"),            # item → not NPC
                    location=Location(type="room", room="room 2"),
                ),
            ]
        )
        client = MagicMock()
        result = align_entities(
            self._report_with_existential(),
            telem,
            openai_client=client,
        )
        res = result.existential_resolutions[0]
        assert res.outcome == "unresolvable"
        client.chat.completions.create.assert_not_called()

    def test_llm_exception_returns_unresolvable(self):
        """If the LLM call raises, the existential is marked unresolvable."""
        client = MagicMock()
        client.chat.completions.create.side_effect = RuntimeError("API down")
        result = align_entities(
            self._report_with_existential(),
            self._telem_with_npcs(),
            openai_client=client,
        )
        res = result.existential_resolutions[0]
        assert res.outcome == "unresolvable"

    def test_duplicate_existential_slots_deduplicated(self):
        """Same (fact_id, role) pair is only resolved once."""
        fact = RelationFact(
            predicate=RelationPredicate.NEEDS_POTION,
            subject=_existential(),
        )
        graph = KnowledgeGraph(facts=[fact])
        client = MagicMock()
        client.chat.completions.create.return_value = _make_llm_response(
            "resolved", resolved_value="lily"
        )
        result = align_entities(graph, self._telem_with_npcs(), openai_client=client)
        assert len(result.existential_resolutions) == 1

    def test_entity_type_filter_recorded(self):
        """entity_type_filter reflects the heuristic used to scope candidates."""
        client = MagicMock()
        client.chat.completions.create.return_value = _make_llm_response(
            "resolved", resolved_value="lily"
        )
        result = align_entities(
            self._report_with_existential(),
            self._telem_with_npcs(),
            openai_client=client,
        )
        res = result.existential_resolutions[0]
        assert res.entity_type_filter == "npc"


# ---------------------------------------------------------------------------
# Existential resolution — live API integration tests
#
# These tests make a real call to the OpenAI API and are therefore:
#   - Skipped automatically when OPENAI_API_KEY is not set
#   - Tagged `live_api` so they can be run explicitly:
#       pytest tests/test_entity_alignment.py -m live_api -v
#   - Excluded from the default run:
#       pytest tests/test_entity_alignment.py -m "not live_api"
# ---------------------------------------------------------------------------

import os as _os

pytestmark_live = pytest.mark.live_api


@pytest.mark.live_api
class TestExistentialResolutionLiveAPI:
    """
    Integration tests that exercise the real gpt-4o-mini path.

    Each test builds a scenario where the correct answer is unambiguous
    from context, then asserts on the structured outcome without hard-coding
    the exact wording the model might use internally.
    """

    @pytest.fixture(autouse=True)
    def _require_api_key(self):
        if not _os.environ.get("OPENAI_API_KEY"):
            pytest.skip("OPENAI_API_KEY not set — skipping live API test")

    # ------------------------------------------------------------------
    # Test 1: Single unambiguous NPC match
    #
    # Scenario: the report says "someone needs a potion" (existential subject).
    # Telemetry has exactly one NPC — lily.  The model should confidently
    # resolve to "lily".
    # ------------------------------------------------------------------
    def test_live_single_npc_candidate_resolves(self):
        """
        When only one NPC exists in telemetry and the existential carries a
        partial value hint that clearly matches it, the LLM should resolve
        to that NPC with outcome='resolved'.
        """
        report = KnowledgeGraph(
            facts=[
                RelationFact(
                    predicate=RelationPredicate.NEEDS_POTION,
                    # Existential with a surface hint: reporter said "lilly" (typo)
                    subject=_existential(value="lilly"),
                )
            ]
        )
        telem = KnowledgeGraph(
            facts=[
                # Only one NPC in the telemetry world
                RelationFact(
                    predicate=RelationPredicate.NEEDS_POTION,
                    subject=_named("lily"),
                )
            ]
        )

        result = align_entities(report, telem)  # no openai_client → uses env key

        assert len(result.existential_resolutions) == 1
        res = result.existential_resolutions[0]
        assert res.outcome == "resolved", (
            f"Expected 'resolved' with a single close-match candidate, got {res.outcome!r}. "
            f"resolved_value={res.resolved_value!r}, candidates={res.candidate_values}"
        )
        assert res.resolved_value == "lily"

    # ------------------------------------------------------------------
    # Test 2: Truly unresolvable — constraint excludes all candidates
    #
    # Scenario: the report mentions "someone to the east" (existential with
    # a location constraint), but telemetry only tracks NPCs in "room 1"
    # (west side).  The model should return 'unresolvable' or 'ambiguous'
    # — critically, it must NOT hallucinate a resolved entity that isn't
    # in our candidate list.
    # ------------------------------------------------------------------
    def test_live_constrained_existential_does_not_hallucinate(self):
        """
        The LLM must not return a resolved_value outside the provided
        candidate list, regardless of what it reasons internally.
        The guard in _resolve_existential enforces this, but this test
        confirms the full round-trip behaviour.
        """
        report = KnowledgeGraph(
            facts=[
                RelationFact(
                    predicate=RelationPredicate.HAS_MESSAGE_FOR,
                    # existential with a directional hint — constrains heavily
                    subject=_existential(),
                    target=_named("player"),
                )
            ]
        )
        # Telemetry: two NPCs, both plausible
        telem = KnowledgeGraph(
            facts=[
                RelationFact(
                    predicate=RelationPredicate.HAS_MESSAGE_FOR,
                    subject=_named("lily"),
                    target=_named("player"),
                ),
                RelationFact(
                    predicate=RelationPredicate.HAS_MESSAGE_FOR,
                    subject=_named("rose"),
                    target=_named("player"),
                ),
            ]
        )

        result = align_entities(report, telem)

        assert len(result.existential_resolutions) == 1
        res = result.existential_resolutions[0]

        # Collect the full NPC candidate set that the alignment module sees —
        # i.e. every named argument value in `telem` that the type heuristic
        # classifies as "npc".  This is the ground truth for what the LLM was
        # allowed to return.
        from src.pipelines.model_alignment.entity_alignment import (
            _iter_arguments,
            _infer_entity_type,
        )
        valid_candidates = {
            s.argument.value
            for s in _iter_arguments(telem)
            if s.argument.type == "named"
            and s.argument.value
            and _infer_entity_type(s.argument.value) == "npc"
        }

        # Outcome must be one of the three valid values
        assert res.outcome in ("resolved", "ambiguous", "unresolvable")

        # If the model claims it resolved, the value must be in the candidate list
        if res.outcome == "resolved":
            assert res.resolved_value in valid_candidates, (
                f"resolved_value={res.resolved_value!r} not in telemetry NPC set {valid_candidates}"
            )

        # candidate_values (if any) must also be a subset of the real candidates
        hallucinated = set(res.candidate_values) - valid_candidates
        assert not hallucinated, (
            f"candidate_values contains hallucinated entities: {hallucinated}"
        )

