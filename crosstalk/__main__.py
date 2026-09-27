"""Command-line entry point for crosstalk."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional, Sequence

from .reader import KernelReader
from .render import write_timeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="View an EASTER handoff chain")
    parser.add_argument("--db", required=True, type=Path, help="EASTER kernel database")
    parser.add_argument("--stream", required=True, help="stream payload marker")
    parser.add_argument("--out", type=Path, default=Path("timeline.html"))
    parser.add_argument(
        "--verify",
        action="store_true",
        help="verify chain integrity (reserved for Phase 2)",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    lineage = KernelReader(args.db).read_stream(args.stream)
    if args.verify:
        from .verify import verify

        result = verify(lineage)
        for problem in result.problems:
            print(problem)
        return 0 if result.valid else 1
    write_timeline(lineage, args.out)
    print("wrote {}".format(args.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
