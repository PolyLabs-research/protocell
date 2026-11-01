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
lamp world passed as preregistered; the spot passed after one geometric amendment; W1–W6 pass in both
(`docs/data/stage0/`). The world from stage 1 on is a cave pool on a 24-hour cycle (D3): its preregistration is
drafted (`docs/prereg/cave.md`) with its numbers set by rules and a probe (`experiments/cave_geometry.py`); its open
points await the owner before it is built.

## Running

    uv venv --python 3.11 .venv && uv pip install --python .venv/bin/python -e ".[dev]"
    .venv/bin/python -m pytest -q
    .venv/bin/python -W error::RuntimeWarning -m experiments.stage0 --workers 16   # stage 0's checks, from a clean tree

## Watching a cell

    .venv/bin/python -m tools.replay --config burn --start 51 --cells b0 b2r b2rr
    xdg-open replays/burn-start51-B0-B2r-B2rr.html

A replay reruns up to three cells from one start of the cave pool, with the checks' code, seed and noise, and writes
a page that plays their lifetimes back: the pool with its light and each cell's track, the chosen cell's body (the
light at each wall node, each cilium's beat, the core's activity), and the reserve and damage over the lifetime.
`.venv/bin/python -m tools.replay --help` lists the cells: the baselines, the cave's random genomes, and genomes from
a `.npy` file (stage 1's evolved cells). Replays go to `replays/`, which git ignores. A link ending `#h10` opens a
replay ten hours in.

`docs/network.html` shows the network's structure: who connects to whom, the mask, which number of the genome sets
which weight, and one tick of the dynamics. It is generated from the code; regenerate it after any change to the
cell with `.venv/bin/python -m tools.network_doc`.

## The code

The package: `protocell/config.py` (every preregistered number), `world.py` (the dish, the two light fields, the
starts), `cell.py` (the genome, the topology mask, the two spoke modes, the CTRNN's step), `motion.py` (the cilia),
`energy.py`, `sim.py` (a whole population at once; the baselines and the network cell as controllers; keyed noise).
`experiments/stage0.py` runs the checks and writes its tables, `summary.json` and `manifest.json` to
`docs/data/stage0/`.
