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
from typing import Sequence

from .reader import Lineage


@dataclass(frozen=True)
class VerificationResult:
    """The planned public result shape for chain verification."""

    valid: bool
    problems: Sequence[str]


def verify(lineage: Lineage) -> VerificationResult:
    """Verify *lineage* according to this module's contract.

    This Phase 1 stub is intentionally unimplemented.
    """
    raise NotImplementedError("verify.py is reserved for Phase 2")
