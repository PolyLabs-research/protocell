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

**Status:** stage 0 (the world, the cell, its energy and the baselines) built and checked (D2, 2026-11-01): the
lamp world passed as preregistered; the spot passed after one geometric amendment (A1: narrower, with starts where a
still cell starves); W1–W6 pass in both (`docs/data/stage0/`). The reflex's score is stage 1's bar. Awaiting the
owner's decisions in D2 before stage 1 is preregistered.

## Running

    uv venv --python 3.11 .venv && uv pip install --python .venv/bin/python -e ".[dev]"
    .venv/bin/python -m pytest -q
    .venv/bin/python -W error::RuntimeWarning -m experiments.stage0 --workers 16   # stage 0's checks, from a clean tree

The package: `protocell/config.py` (every preregistered number), `world.py` (the dish, the two light fields, the
starts), `cell.py` (the genome, the topology mask, the two spoke modes, the CTRNN's step), `motion.py` (the cilia),
`energy.py`, `sim.py` (a whole population at once; the baselines and the network cell as controllers; keyed noise).
`experiments/stage0.py` runs the checks and writes its tables, `summary.json` and `manifest.json` to
`docs/data/stage0/`.
