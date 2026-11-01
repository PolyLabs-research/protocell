# Determinism

The claim: **the same code, settings and seed on the same platform give the same bits.** Nothing is claimed across
platforms yet; that would need a stated tolerance, as quantum-rat's CI has.

## Rules

1. **One BLAS thread.** Importing `protocell` sets `OMP_NUM_THREADS` and its siblings to 1 before numpy loads
   (`protocell/__init__.py`), since threaded reductions can reorder a floating-point sum. Import `protocell` before
   `numpy` in every entry point. Parallelism comes from processes.
2. **Named streams.** Every source of randomness draws from its own stream, `protocell.rng.stream(seed, name)`, so
   switching one source off or adding one never shifts another's draws. The streams in use are listed in
   `protocell/rng.py`; their first values are pinned by a test. A stream switched off is not drawn from at all.
3. **A batch equals its singles.** A population simulated at once in arrays must reproduce each cell's run alone, bit
   for bit (stage 0's check W6). What makes it so: each cell's noise comes from its own keyed stream,
   `stream(seed, name, (cell, start))`; sums over neurons run in a fixed order (`protocell.cell.batched_matvec`); and
   arithmetic over tiny axes (a position's two components, a distance) is written out by component rather than
   reduced, so no numpy reduction's blocking can differ between one row and many.
4. **Provenance.** Every run writes `manifest.json` beside its data (`protocell/manifest.py`): the commit and whether
   the tree was dirty, the settings, the seeds, the platform and BLAS in force, the command, the wall time.
5. **Runs that produce results** are made from a clean tree with numerical warnings as errors
   (`python -W error::RuntimeWarning`), and no tracked file is edited while one is in flight (the manifest reads the
   tree's state).
