"""Render a crosstalk lineage as a self-contained HTML timeline."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any, Mapping

from .reader import Lineage


def _pretty(value: Any) -> str:
    return html.escape(json.dumps(value, indent=2, sort_keys=True))


def _identity_label(
    transition: Mapping[str, Any], identities: Mapping[str, Mapping[str, Any]]
) -> str:
    actor = transition["payload"].get("requester_identity_id") or transition[
        "payload"
    ].get("identity_id")
    if not actor:
        return "unknown agent"
    identity = identities.get(actor, {})
    label = identity.get("payload", {}).get("name")
    return "{} ({})".format(label, actor) if label else str(actor)


def render_html(lineage: Lineage) -> str:
    """Return a complete, dependency-free HTML document for *lineage*."""
    receipts = {row["transition_id"]: row for row in lineage.receipts}
    evidence_by_receipt = {}
    for record in lineage.evidence:
        evidence_by_receipt.setdefault(record["receipt_id"], []).append(record)
    states = {row["state_id"]: row for row in lineage.states}
    identities = {row["identity_id"]: row for row in lineage.identities}

    cards = []
    for transition in lineage.transitions:
        receipt = receipts.get(transition["transition_id"])
        linked = evidence_by_receipt.get(
            receipt["receipt_id"] if receipt else "", []
        )
        evidence_html = "".join(
            "<li><code>{}</code><pre>{}</pre></li>".format(
                html.escape(item["evidence_id"]), _pretty(item["payload"])
            )
            for item in linked
        ) or "<li>None</li>"
        to_state = states.get(transition["to_state_id"], {})
        receipt_html = (
            "<p><strong>Receipt:</strong> <code>{}</code> "
            "<span class='outcome'>{}</span></p><pre>{}</pre>".format(
                html.escape(receipt["receipt_id"]),
                html.escape(receipt["outcome"]),
                _pretty(receipt["payload"]),
            )
            if receipt
            else "<p class='missing'><strong>Receipt:</strong> missing</p>"
        )
        cards.append(
            """<article class="event">
<h2>{transition_id}</h2>
<p class="meta">{created_at} · {agent}</p>
<p><code>{from_id}</code> → <code>{to_id}</code></p>
<h3>Transition</h3><pre>{transition_payload}</pre>
<h3>State</h3><pre>{state_payload}</pre>
{receipt}
<h3>Evidence</h3><ul>{evidence}</ul>
</article>""".format(
                transition_id=html.escape(transition["transition_id"]),
                created_at=html.escape(transition["created_at"]),
                agent=html.escape(_identity_label(transition, identities)),
                from_id=html.escape(transition["from_state_id"]),
                to_id=html.escape(transition["to_state_id"]),
                transition_payload=_pretty(transition["payload"]),
                state_payload=_pretty(to_state.get("payload", {})),
                receipt=receipt_html,
                evidence=evidence_html,
            )
        )

    return """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Crosstalk timeline: {stream}</title>
<style>
:root {{ color-scheme: light dark; font-family: system-ui, sans-serif; }}
body {{ max-width: 900px; margin: 2rem auto; padding: 0 1rem; line-height: 1.5; }}
header {{ border-bottom: 2px solid currentColor; margin-bottom: 2rem; }}
.event {{ border-left: 4px solid #6487dc; padding: .25rem 1rem 1rem; margin: 0 0 1.5rem; }}
.meta {{ opacity: .72; }} pre {{ overflow: auto; padding: .75rem; background: rgba(127,127,127,.12); }}
code {{ overflow-wrap: anywhere; }} .missing {{ color: #b33; }} .outcome {{ font-weight: 700; }}
</style></head><body>
<header><h1>{stream}</h1><p>{states} states · {transitions} transitions · {receipts} receipts</p></header>
<main>{cards}</main>
</body></html>""".format(
        stream=html.escape(lineage.stream),
        states=len(lineage.states),
        transitions=len(lineage.transitions),
        receipts=len(lineage.receipts),
        cards="\n".join(cards) or "<p>No transitions.</p>",
    )


def write_timeline(lineage: Lineage, output: Path) -> None:
    """Write *lineage* to *output* as UTF-8 HTML."""
    Path(output).write_text(render_html(lineage), encoding="utf-8")
