# protocell

A single cell whose wall and brain are one neural network, evolved to manage light.

The cell's wall is a ring of neural nodes daisy-chained in a closed loop; each node senses the light at its place on
the membrane, beats a cilium, and connects both ways into a small central network. Wall and core are one recurrent
network. Light is food, too much light harms, and the cell has to find and hold a good place in it. The wiring is
evolved, as a single cell's is.

The project tests, from first principles, the hypothesis that behaviour emerges from the interaction of parts:
starting with the simplest organism and few parts, each understood, and adding complexity only when a test needs it.

- `docs/plan.md`: the plan and its stages
- `docs/decisions.md`: the decisions log (D1, D2, ...)
- `docs/prereg/`: a preregistration before every build and run
- `docs/determinism.md`: what is claimed about reproducibility, and the rules

**Status:** stage 0 (the world, the cell, its energy and the baselines) preregistered as a draft; the scaffolding
built.

## Running

    uv venv --python 3.11 .venv && uv pip install --python .venv/bin/python -e ".[dev]"
    .venv/bin/python -m pytest -q
