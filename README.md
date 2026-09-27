# crosstalk

**CROSSTALK-0 experiment.** A handoff-chain viewer for EASTER governed-state
kernels: it reads a kernel database and renders the lineage of a cross-agent
build as a timeline — who did what, where the handoffs landed, and whether the
chain verifies end to end.

The experiment: this app is being built *by handoff*. Hermes (Mac) builds the
reader; Clawde (Linux) discovers this repo **only** through an EASTER kernel
lookup — no prior knowledge of the URL, the stack, or the plan — and continues
the build. The demo data is the experiment itself: the app narrates its own
construction.

Coordination lives in the kernel, stream `crosstalk-0`. This repo is the work
medium, not the coordination channel.

## Stack

Python 3, standard library only (`sqlite3`, `argparse`, `html`). No
dependencies — both build machines run it untouched.

## Layout (planned)

- `crosstalk/reader.py` — parse a kernel DB, extract a stream's lineage
  (states, transitions, receipts)
- `crosstalk/render.py` — render the lineage as a static HTML timeline
- `crosstalk/verify.py` — verify chain integrity (no gaps, receipts account
  for every transition)
- `tests/` — fixture-DB tests for reader and verifier

## Usage (planned)

```bash
python -m crosstalk --db kernel.db --stream crosstalk-0 --out timeline.html
python -m crosstalk --db kernel.db --stream crosstalk-0 --verify
```
