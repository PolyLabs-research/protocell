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
- `docs/stages-4-5.md`: stages 4 to 7 written up: the cells that beat every simple rule at home, and how far that travels
- `docs/prereg/`: a preregistration before every build and run
- `docs/determinism.md`: what is claimed about reproducibility, and the rules

**Status:** stage 0 built and checked (D2). The cave pool, the world from stage 1 on, built and checked (D4, 2026-11-01): a south-facing
cave's pool on a 24-hour cycle, at a 1 s tick, with damage and the sun's sweep as switches. All four configurations pass
K1–K7 after one amendment to the damage reflex's rule (`docs/prereg/cave.md` §17; `docs/data/cave/`). The owner's decisions
(D5): the cave is stage 1's world, evolved in day first, both spoke modes, fitness as the bar. Stage 1 ran (D7, 2026-11-02): evolution
in the cave's day configuration on RunPod, three runs per spoke mode. Every champion survives, but none reaches the
reflex's fitness (the best falls 0.011 short), and every one depends on its core, the core's recurrence and the ring's
links. Stage 1b (D9): holding any of those parts at
its average also breaks every champion, so each part's moment-to-moment signal matters. Stage 3a (D10): the translucent cell's
world passes every check; without shading the reflex survives a third of its starts, while a cell that compares
its light over time (B5) survives all of them. Stage 3b (D11): comparing over time
evolved only sometimes and partly (the best champion recovers 39% of what memory is worth over the reflex), and its
best form scores far below B5. Stage 3c (D14): the uniform cell reads the light's direction with
its ring, confirmed by changing what it senses; neither stage 3b champion compares over time (D11 corrected). Stage 4's
probes (D16): changing light alone leaves no room above the simple rules, a tighter economy does. Stage 4a (D17):
that world passes its checks. Stage 4b's pilots (D18, D19): this search does not
reach a working cell there, even one change at a time. Stage 4c's pilot (D20): CMA-ES, a stronger search, does no
better; neither search makes a working cell thrifty. The thrift probe (D22): the working cells die mainly by finding
too little light, about half of B8's, not by spending. Stage 4d (D23): a cell fitted to B8's beats by CMA-ES stalls at a
match of 0.31 and does not carry B8, which leaves open whether the cell could. Stage 4e (D25): cells written by hand in both modes
do not carry B8 either; the notebooks point at the cell's wiring (it senses only through its beats and has no gain
control). Stage 5 (D26): a cell that senses light relative to its recent level. Stage 5b (D27): written by hand on that cell, a fourier1 cell carries B8 on fresh starts, narrowly (0.909 of the gap, interval 0.850–0.965), and a uniform cell partly (0.618). Stage 5c (D28, D29): a search that starts at that hand-written cell and moves each gene about 1% finds cells that beat B8 on fresh starts in 2 of 3 runs (0.593 and 0.610 against 0.557), the first result for the hypothesis's strong sense, from a designed start. The explaining probe (D31): the search retuned the hand-written mechanism, mostly the core's links, into a cell that crosses the dark about twice as fast and holds a rising run more firmly. Stages 4 to 7 are written up in `docs/stages-4-5.md`. Stage 6 (D33): evolution from random genomes on that cell, in fourier1 mode, finds a cell that does B8's job in 2 of 3 runs, and one of them beats B8 (0.588 against 0.538); the uniform mode still fails. Stage 6b (D37): five more such runs at 400 generations: 4 of 5 do B8's job and 2 of 5 beat it (the best scores 0.642 against 0.558), and every run is better at 400 generations than at 200. Stage 7 (D40): in six worlds they never saw, the cells match each world's best simple rule where the world is like home and mostly fail where it is not (flickering clouds, a circling spot, self-shading); one evolved cell holds up in all of them. Stage 8 (D42): evolved from random genomes in four of those worlds at once, one run in five gives a generalist, a cell that does the best simple rule's job in eight of nine worlds and beats it in five, two of them worlds it never met.

## Running

    uv venv --python 3.11 .venv && uv pip install --python .venv/bin/python -e ".[dev]"
    .venv/bin/python -m pytest -q
    .venv/bin/python -W error::RuntimeWarning -m experiments.stage0 --workers 16   # stage 0's checks, from a clean tree
    .venv/bin/python -W error::RuntimeWarning -m experiments.cave --config all --workers 16   # the cave's checks (about 95 min)

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

## Running on RunPod

Stage 1's runs go on RunPod CPU pods (docs/prereg/stage1.md §13), under the chess project's lifecycle library: the
pod's deadline watchdog, the sweeper timer on this box, the budget check and the ledger. The owner confirms the
flavour, the rate ceiling, the hours and the worst cost before every launch.

    .venv/bin/python cloud/cpu_pod.py launch --tag protocell-pilot --flavor cpu5c --vcpu 32 --hours 4 --max-rate 2.24   # dry run; --yes creates it
    (cd ~/Documents/dev/chess && .venv/bin/python scripts/runpod_pod.py wait-ssh POD_ID)
    bash cloud/stage_pod.sh POD_ID     # pushes this commit, installs, runs the tests, measures the cost a tick

The chess tool's `status`, `ssh`, `push`, `pull` and `terminate POD_ID` work on any `taz-` pod. Never use its
`terminate --all-ours` here: the chess project's own pods carry the same prefix.

## The code

The package: `protocell/config.py` (every preregistered number: `STAGE0`, and `CAVE` at a 1 s tick), `world.py` (the
dish, stage 0's spot and lamp, the cave's mouth with its day and sweep, the starts and their phases), `cell.py` (the
genome, the topology mask, the two spoke modes, the CTRNN's step), `motion.py` (the cilia), `energy.py` (with damage
and the cave's matched reserve), `sim.py` (a whole population at once; the baselines and the network cell as
controllers; keyed noise; an observer for replays). `experiments/stage0.py` and `experiments/cave.py` run the checks
and write their tables, `summary.json` and `manifest.json` to `docs/data/stage0/` and `docs/data/cave/`.
