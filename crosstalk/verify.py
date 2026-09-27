"""Chain-integrity verification contract for the second handoff phase.

``verify(lineage)`` must return a result describing every integrity problem,
without stopping at the first one. It must check that each transition's source
and destination state is present, every non-boundary state has exactly one
incoming transition, every included transition has exactly one ACCEPTED
receipt, no receipt names an absent transition, and each receipt/evidence link
resolves to an included evidence record. Branches are valid and must not be
collapsed into a canonical head. The implementation and fixture-DB tests are
intentionally reserved for the receiving agent.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Sequence

from .reader import Lineage


@dataclass(frozen=True)
class VerificationResult:
    """The planned public result shape for chain verification."""

    valid: bool
    problems: Sequence[str]


def _is_boundary(state: Mapping[str, Any], stream: str) -> bool:
    """A boundary state is included only because a transition crosses into
    *stream* from outside it; it carries no tag for *stream* itself."""
    payload = state["payload"]
    return payload.get("stream", payload.get("stream_id")) != stream


def verify(lineage: Lineage) -> VerificationResult:
    """Verify *lineage* according to this module's contract."""
    problems: List[str] = []

    state_ids = {row["state_id"] for row in lineage.states}
    transition_ids = {row["transition_id"] for row in lineage.transitions}
    receipt_ids = {row["receipt_id"] for row in lineage.receipts}

    for transition in lineage.transitions:
        transition_id = transition["transition_id"]
        if transition["from_state_id"] not in state_ids:
            problems.append(
                "{}: source state {} is not included in the lineage".format(
                    transition_id, transition["from_state_id"]
                )
            )
        if transition["to_state_id"] not in state_ids:
            problems.append(
                "{}: destination state {} is not included in the lineage".format(
                    transition_id, transition["to_state_id"]
                )
            )

    incoming: Dict[str, int] = {}
    for transition in lineage.transitions:
        to_state_id = transition["to_state_id"]
        incoming[to_state_id] = incoming.get(to_state_id, 0) + 1

    for state in lineage.states:
        if _is_boundary(state, lineage.stream):
            continue
        state_id = state["state_id"]
        count = incoming.get(state_id, 0)
        if count != 1:
            problems.append(
                "{}: has {} incoming transitions, expected exactly 1".format(
                    state_id, count
                )
            )

    for transition in lineage.transitions:
        transition_id = transition["transition_id"]
        accepted = sum(
            1
            for receipt in lineage.receipts
            if receipt["transition_id"] == transition_id
            and receipt["outcome"] == "ACCEPTED"
        )
        if accepted != 1:
            problems.append(
                "{}: has {} ACCEPTED receipts, expected exactly 1".format(
                    transition_id, accepted
                )
            )

    for receipt in lineage.receipts:
        if receipt["transition_id"] not in transition_ids:
            problems.append(
                "{}: names transition {} which is not included in the lineage".format(
                    receipt["receipt_id"], receipt["transition_id"]
                )
            )

    for record in lineage.evidence:
        if record["receipt_id"] not in receipt_ids:
            problems.append(
                "{}: linked receipt {} is not included in the lineage".format(
                    record["evidence_id"], record["receipt_id"]
                )
            )

    return VerificationResult(valid=not problems, problems=tuple(problems))
