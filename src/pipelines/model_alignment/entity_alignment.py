"""
Entity alignment step for the model-alignment pipeline.

Aligns named entities across two KnowledgeGraph objects (report vs telemetry)
and attempts to resolve existential Arguments to named telemetry entities.

Public API
----------
align_entities(report_graph, telemetry_graph, *, openai_client=None)
    -> AlignmentResult

The `openai_client` parameter is optional; pass a pre-configured `openai.OpenAI`
instance to avoid environment variable look-up (useful in tests).  If omitted
and existentials are present, the client is created lazily from OPENAI_API_KEY.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Literal

import dotenv

from src.core.representations.pydantic_schema import (
    Argument,
    ConnectionFact,
    Fact,
    KnowledgeGraph,
    LocationFact,
    RelationFact,
    SpatialFact,
)

dotenv.load_dotenv()

log = logging.getLogger(__name__)

from src.core.utils.normalization import normalize_entity_name as _normalize, _ALIAS_TABLE


# ---------------------------------------------------------------------------
# Simple entity-type heuristic
# ---------------------------------------------------------------------------
_ITEM_KEYWORDS = ("potion", "key", "chest", "scroll", "gem", "coin", "sword")
_LOCATION_KEYWORDS = ("room", "corridor", "hall", "vault", "chamber", "area")


def _infer_entity_type(value: str) -> Literal["item", "location", "npc"]:
    """Heuristic entity type from a surface-form string."""
    lower = value.lower()
    if any(kw in lower for kw in _ITEM_KEYWORDS):
        return "item"
    if any(kw in lower for kw in _LOCATION_KEYWORDS):
        return "location"
    return "npc"


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class ExistentialResolution:
    """Resolution outcome for one existential Argument found in the report graph."""

    #: Fact ID that contains the existential argument.
    source_fact_id: str
    #: Which slot held the existential (e.g. "subject", "object", "target",
    #: "entity", "reference").
    argument_role: str
    #: "resolved"    → a single telemetry entity was confidently matched;
    #: "ambiguous"   → multiple candidates remain after LLM reasoning;
    #: "unresolvable" → no telemetry entity satisfies the constraints.
    outcome: Literal["resolved", "ambiguous", "unresolvable"]
    #: The matched entity value when outcome == "resolved".
    resolved_value: str | None = None
    #: Narrowed candidate set when outcome == "ambiguous".
    candidate_values: list[str] = field(default_factory=list)
    #: The entity type used to scope the telemetry candidate list.
    entity_type_filter: str | None = None


@dataclass
class AlignmentResult:
    """
    Complete alignment output for one (report_graph, telemetry_graph) pair.

    named_mapping
        Maps report named-entity *values* to their canonical telemetry
        counterpart.  Only entities that were successfully matched are
        included; unmatched named entities are simply absent from the dict
        (they may be genuinely novel).

    existential_resolutions
        One entry per existential Argument found anywhere in report_graph.
    """

    named_mapping: dict[str, str] = field(default_factory=dict)
    existential_resolutions: list[ExistentialResolution] = field(default_factory=list)


# Normalization helper _normalize is imported from src.core.utils.normalization


def _match_named(report_value: str, telem_by_norm: dict[str, str]) -> str | None:
    """
    Try to match a report entity value against the telemetry entity set.

    Resolution order:
    1. Exact string match (already handled by the caller via norm == norm)
    2. Normalised match
    3. Alias lookup → then normalised match
    """
    norm = _normalize(report_value)

    # Normalised match (covers exact + case/space/underscore variants)
    if norm in telem_by_norm:
        return telem_by_norm[norm]

    # Alias → normalised match
    canonical = _ALIAS_TABLE.get(norm)
    if canonical is not None:
        canon_norm = _normalize(canonical)
        if canon_norm in telem_by_norm:
            return telem_by_norm[canon_norm]

    return None


# ---------------------------------------------------------------------------
# Argument collection helpers
# ---------------------------------------------------------------------------

@dataclass
class _ArgSlot:
    fact_id: str
    argument_role: str
    argument: Argument
    fact: Fact


def _iter_arguments(graph: KnowledgeGraph) -> list[_ArgSlot]:
    """Yield every Argument in the graph together with its fact_id and role."""
    slots: list[_ArgSlot] = []
    for fact in graph.facts:
        fid = fact.id  # type: ignore[union-attr]
        if isinstance(fact, RelationFact):
            for role, arg in [
                ("subject", fact.subject),
                ("object", fact.object),
                ("target", fact.target),
            ]:
                if arg is not None:
                    slots.append(_ArgSlot(fid, argument_role=role, argument=arg, fact=fact))
        elif isinstance(fact, LocationFact):
            slots.append(_ArgSlot(fid, argument_role="entity", argument=fact.entity, fact=fact))
        elif isinstance(fact, SpatialFact):
            slots.append(_ArgSlot(fid, argument_role="subject", argument=fact.subject, fact=fact))
            if fact.reference is not None:
                slots.append(_ArgSlot(fid, argument_role="reference", argument=fact.reference, fact=fact))
        elif isinstance(fact, ConnectionFact):
            pass  # ConnectionFact has no Argument slots, only Locations
    return slots


# ---------------------------------------------------------------------------
# Named-entity alignment (deterministic)
# ---------------------------------------------------------------------------

def _build_named_mapping(
    report_graph: KnowledgeGraph,
    telemetry_graph: KnowledgeGraph,
) -> dict[str, str]:
    """
    Build report-value → telemetry-value mapping for named Arguments.
    """
    # Collect all unique named values from telemetry
    telem_named: set[str] = set()
    for slot in _iter_arguments(telemetry_graph):
        if slot.argument.type == "named" and slot.argument.value:
            telem_named.add(slot.argument.value)

    # Index by normalised form (last-write wins for collisions, but canonical
    # names shouldn't collide after normalisation in a constrained domain)
    telem_by_norm: dict[str, str] = {_normalize(v): v for v in telem_named}

    mapping: dict[str, str] = {}
    for slot in _iter_arguments(report_graph):
        if slot.argument.type != "named" or not slot.argument.value:
            continue
        value = slot.argument.value
        if value in mapping:
            continue
        match = _match_named(value, telem_by_norm)
        if match is not None and match != value:
            mapping[value] = match

    return mapping


# ---------------------------------------------------------------------------
# Existential resolution (LLM)
# ---------------------------------------------------------------------------

_EXISTENTIAL_RESOLUTION_SYSTEM = """\
You are an entity-resolution assistant for a constrained text-adventure game.
Given an existential argument (an unknown/underspecified entity) and a list of
candidate named entities from the game telemetry, decide which telemetry entity
(if any) satisfies the constraints.

Respond with a JSON object and NOTHING ELSE.  Schema:
{
  "outcome": "resolved" | "ambiguous" | "unresolvable",
  "resolved_value": "<entity name>" | null,
  "candidate_values": ["<entity1>", ...]   // non-empty only when ambiguous
}

Rules:
- "resolved"      → exactly one candidate satisfies the constraints.
- "ambiguous"     → multiple candidates remain; list them in candidate_values.
- "unresolvable"  → no candidate satisfies the constraints.
- resolved_value must be one of the provided candidates or null.
- candidate_values must be a subset of the provided candidates or empty.
"""


def _build_existential_prompt(
    slot: _ArgSlot,
    candidates: list[str],
    telemetry_graph: KnowledgeGraph | None = None,
) -> str:
    arg = slot.argument
    lines = [
        f"Existential argument in role '{slot.argument_role}' "
        f"(fact id: {slot.fact_id}).",
    ]
    if arg.value:
        lines.append(f"Partial surface form: \"{arg.value}\"")
    if arg.location:
        lines.append(f"Location constraint: {arg.location.model_dump_json()}")
    if slot.fact:
        lines.append(f"Fact context: {slot.fact.model_dump_json(exclude_none=True)}")

    # Extract telemetry facts that mention any of the candidates, plus map connectivity
    telemetry_context = []
    spatial_context = []
    if telemetry_graph is not None:
        for fact in telemetry_graph.facts:
            if isinstance(fact, (ConnectionFact, SpatialFact)):
                spatial_context.append(fact.model_dump_json(exclude_none=True))
                continue
            
            mentions_candidate = False
            for attr in ["subject", "object", "target", "entity", "reference"]:
                val = getattr(fact, attr, None)
                if val is not None:
                    if hasattr(val, "value") and val.value in candidates:
                        mentions_candidate = True
                    elif isinstance(val, str) and val in candidates:
                        mentions_candidate = True
            if mentions_candidate:
                telemetry_context.append(fact.model_dump_json(exclude_none=True))

    if spatial_context:
        lines.append("")
        lines.append("Map connections and spatial layout:")
        for sc in spatial_context:
            lines.append(f"  - {sc}")

    if telemetry_context:
        lines.append("")
        lines.append("Telemetry context (facts about candidates):")
        for tc in telemetry_context:
            lines.append(f"  - {tc}")

    lines.append("")
    lines.append("Telemetry candidates:")
    for c in candidates:
        lines.append(f"  - {c}")
    return "\n".join(lines)


def _resolve_existential(
    slot: _ArgSlot,
    candidates: list[str],
    client: object,  # openai.OpenAI
    telemetry_graph: KnowledgeGraph | None = None,
) -> ExistentialResolution:
    """Call the LLM and parse its JSON response into an ExistentialResolution."""
    entity_type = _infer_entity_type(slot.argument.value or slot.argument_role)

    if not candidates:
        return ExistentialResolution(
            source_fact_id=slot.fact_id,
            argument_role=slot.argument_role,
            outcome="unresolvable",
            entity_type_filter=entity_type,
        )

    prompt = _build_existential_prompt(slot, candidates, telemetry_graph)

    model = os.environ.get("GPT_MODEL", "gpt-4o-mini")
    kwargs = {
        "model": model,
        "text": {"format": {"type": "json_object"}},
        "input": [
            {"role": "system", "content": _EXISTENTIAL_RESOLUTION_SYSTEM},
            {"role": "user", "content": prompt},
        ],
    }
    if "sol" in model or "gpt-5" in model or "o1" in model or "o3" in model:
        kwargs["reasoning"] = {"effort": "medium"}
    else:
        kwargs["temperature"] = 0

    try:
        response = client.responses.create(**kwargs)  # type: ignore[union-attr]
        raw = response.output_text or "{}"
        data: dict = json.loads(raw)
    except Exception as exc:
        log.warning(
            "LLM call failed for existential %s/%s: %s",
            slot.fact_id,
            slot.argument_role,
            exc,
        )
        return ExistentialResolution(
            source_fact_id=slot.fact_id,
            argument_role=slot.argument_role,
            outcome="unresolvable",
            entity_type_filter=entity_type,
        )

    outcome: str = data.get("outcome", "unresolvable")
    resolved_value: str | None = data.get("resolved_value")
    candidate_values: list[str] = data.get("candidate_values") or []

    # Validate outcome value
    if outcome not in ("resolved", "ambiguous", "unresolvable"):
        outcome = "unresolvable"

    # Guard: resolved_value must be one of the candidates
    if outcome == "resolved" and resolved_value not in candidates:
        log.warning(
            "LLM returned resolved_value=%r not in candidates for %s/%s; "
            "marking unresolvable.",
            resolved_value,
            slot.fact_id,
            slot.argument_role,
        )
        outcome = "unresolvable"
        resolved_value = None

    # Guard: candidate_values must be subset of candidates
    candidate_values = [v for v in candidate_values if v in candidates]

    return ExistentialResolution(
        source_fact_id=slot.fact_id,
        argument_role=slot.argument_role,
        outcome=outcome,  # type: ignore[arg-type]
        resolved_value=resolved_value if outcome == "resolved" else None,
        candidate_values=candidate_values if outcome == "ambiguous" else [],
        entity_type_filter=entity_type,
    )


def _resolve_existentials(
    report_graph: KnowledgeGraph,
    telemetry_graph: KnowledgeGraph,
    openai_client: object | None,
) -> list[ExistentialResolution]:
    """Resolve every existential Argument in report_graph against telemetry."""
    # Collect telemetry named values, grouped by inferred type
    telem_by_type: dict[str, list[str]] = {}
    for slot in _iter_arguments(telemetry_graph):
        if slot.argument.type == "named" and slot.argument.value:
            etype = _infer_entity_type(slot.argument.value)
            telem_by_type.setdefault(etype, [])
            if slot.argument.value not in telem_by_type[etype]:
                telem_by_type[etype].append(slot.argument.value)

    # Find existentials in report graph
    existential_slots = [
        s for s in _iter_arguments(report_graph) if s.argument.type == "existential"
    ]

    if not existential_slots:
        return []

    # Lazily create OpenAI client
    client = openai_client
    if client is None:
        try:
            from openai import OpenAI  # type: ignore
            client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        except Exception as exc:
            log.error("Could not create OpenAI client: %s", exc)
            return [
                ExistentialResolution(
                    source_fact_id=s.fact_id,
                    argument_role=s.argument_role,
                    outcome="unresolvable",
                )
                for s in existential_slots
            ]

    resolutions: list[ExistentialResolution] = []
    seen: set[tuple[str, str]] = set()  # (fact_id, role) dedup

    for slot in existential_slots:
        key = (slot.fact_id, slot.argument_role)
        if key in seen:
            continue
        seen.add(key)

        # Entity type hint from partial value or location
        partial = slot.argument.value or ""
        hint_text = partial or slot.argument_role
        etype = _infer_entity_type(hint_text)

        # Narrow by location constraint if present
        candidates = list(telem_by_type.get(etype, []))

        resolution = _resolve_existential(slot, candidates, client, telemetry_graph)
        resolutions.append(resolution)

    return resolutions


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def align_entities(
    report_graph: KnowledgeGraph,
    telemetry_graph: KnowledgeGraph,
    *,
    openai_client: object | None = None,
) -> AlignmentResult:
    """
    Align named entities and resolve existentials across two KnowledgeGraph
    objects.

    Parameters
    ----------
    report_graph:
        The graph extracted from the human verbal report.
    telemetry_graph:
        The reference graph derived from game telemetry (treated as ground truth
        for entity names).
    openai_client:
        Optional pre-configured ``openai.OpenAI`` instance.  If *None* and the
        graph contains existential arguments, an instance is created lazily from
        the ``OPENAI_API_KEY`` environment variable.

    Returns
    -------
    AlignmentResult
    """
    named_mapping = _build_named_mapping(report_graph, telemetry_graph)
    existential_resolutions = _resolve_existentials(
        report_graph, telemetry_graph, openai_client
    )
    return AlignmentResult(
        named_mapping=named_mapping,
        existential_resolutions=existential_resolutions,
    )


__all__ = [
    "align_entities",
    "AlignmentResult",
    "ExistentialResolution",
]
