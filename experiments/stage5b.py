"""Stage 5b (docs/prereg/stage5.md §4): stage 4e's hand-writing test, exactly, on the cell that senses light relative to
its recent level (stage5.md §2). The tool is stage 4e's (``experiments.stage4e``); only the world's cell, the judge's
fresh starts (seed 29), the bootstrap (seed 30) and the folder (docs/data/stage5b/) differ.

    .venv/bin/python -m experiments.stage5b probe DESIGN.json step --level 1 --rise 0.02 --noise
    .venv/bin/python -W error::RuntimeWarning -m experiments.stage5b check DESIGN.json --trace 30
    .venv/bin/python -m experiments.stage5b note --mode fourier1 "what the check taught"
    .venv/bin/python -W error::RuntimeWarning -m experiments.stage5b judge DESIGN.json
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional, Sequence

import protocell  # noqa: F401  # pins the BLAS thread counts before numpy loads

from experiments import stage4a, stage4e
from protocell.config import Config

ADAPT_TAU, SENSE_FLOOR = 10.0, 0.1  # stage5.md §2
JUDGE_SEED, BOOTSTRAP_SEED = 29, 30  # fresh
DEFAULT_OUT = Path("docs/data/stage5b")


def world(quick: bool = False) -> Config:
    """Stage 4a's world with stage 5's cell."""
    return stage4a.world(quick).but(sensing="relative", adapt_tau=ADAPT_TAU, sense_floor=SENSE_FLOOR)


STAGE5B = stage4e.Stage("stage5b", world, JUDGE_SEED, BOOTSTRAP_SEED, DEFAULT_OUT)


def main(argv: Optional[Sequence[str]] = None) -> Any:
    return stage4e.main(argv, STAGE5B)


if __name__ == "__main__":
    main(sys.argv[1:])
