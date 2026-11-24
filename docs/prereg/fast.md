# Plan: a compiled life for the searches

**Written:** 2026-11-24, after the owner's decision D46 (the generalist's reliability run is to run on his laptop, not
RunPod), before the check in §4 ran. `docs/decisions.md` D47 records it.

## 1. Why

- **Nothing in the project used a GPU, or could.** The simulation is NumPy on the CPU: each tick is about a hundred
  small array operations, and a generation's work is spread over processes.
- **A run is long because of that per-tick overhead, not because of the arithmetic.** A stage 8 run is 400 generations
  of 768 lives, each up to 172,800 ticks. On a 16-vCPU pod its generations took 83–111 s (`generations.csv`), so 9 to
  10 hours a run.
- **Measured here before this plan, on one core (scratch runs, not results):** the reference costs 4–8 microseconds a
  cell-tick in a batch of 48; the same life written as scalar code and compiled costs 0.5–0.9.

## 2. What is built

`protocell/fast.py`: one cell's whole life as scalar code, compiled by Numba.

- **The same model.** Every operation of the reference's tick, in the reference's order: sense, the network's step,
  the cilia, the move, energy, damage, the death check. Sums over the wall's nodes are added in numpy's order.
- **The same luck.** Each start's sensor noise, rotation noise, sky and light source are drawn or computed beforehand
  by the reference's own streams and functions.
- **Not the same library functions.** numpy's `exp`, `log`, `sin` and `cos` are its own vectorised ones; the compiled
  life calls the C library's. They differ in the last bit now and then. By default the kernel also gets each node's
  direction from the heading's sine and cosine by the angle-sum rule: 2 calls a tick where the reference makes 64.
- **So single lives part.** A life is chaotic: a last bit grows until the two engines' cells are in different places.
  The claim is agreement in distribution and in ranking, not life by life.
- **Only what a search needs:** the cave, the network cell, absolute or relative sensing. Anything else is refused.
- **The searches are untouched.** `fast.Mapper` wraps the mapper a search is given and swaps in the compiled life for
  the searches' two jobs (a generation's training lives, and the validation that picks a run's champion).
- **A GPU form** (`protocell/fast_cuda.py`): the same function compiled for an Nvidia GPU, one thread a life, double
  precision. This machine has no Nvidia GPU, so here it is compiled (NVIDIA's compiler runs without a device) and
  run in Numba's simulator, which executes the kernel as plain Python. It has not run on a GPU.

## 3. What it is for, and what stays on the reference

- **For:** the searches' lives, on the CPU or a GPU.
- **Not for:** any test or reported number. Every champion is still judged by `protocell.sim.simulate` on fresh
  starts, as in every stage so far. A run made on the compiled life says so in its manifest.
- **A new dependency,** optional: `pip install -e ".[fast]"` (Numba) for the CPU, `".[gpu]"` for an Nvidia GPU
  (Numba, and NVIDIA's compiler and runtime from PyPI; the machine needs only NVIDIA's driver). Without either the
  project is as it was.

## 4. The check (`experiments/fastcheck.py`), and what it must show

One process here, about an hour. Seeds 50 (starts), 51 (intervals), 52 and 53 (two draws of training starts): none
used before.

**The worlds:** the six a stage 8 run meets: home, flicker, spot, shaded, and a generation from each half of the
eased-in path (generation 25: part shaded, the cave's gain; generation 75: translucent, the gain falling).

**A. The same model.** With numpy's `exp`, `log`, `sin` and `cos` replaced by the C library's and the kernel in its
strict form (each node's direction computed as the reference computes it), whole lives must be the reference's bit for
bit: two cells (champion 8102, and a cell from the end of its run's population) on a daytime and a night start in each
world, 24 lives. *Criterion: all 24 identical in every number.*

**B. The same outcomes.** The kernel as the searches use it, beside the reference as it is.
- Three cells (champions 8102, 6402 and 8105) on 100 fresh starts in each world: 18 cell-and-world pairs, 1,800 paired
  lives, the same starts and noise for both engines.
- A whole population (the 96 genomes at the end of run 8102) scored as a search scores a generation: 8 training
  starts, 2 from each trained world, under two draws of luck (seeds 52 and 53).

*Criteria:*
- **B1:** in every pair the two engines' mean fitness differ by less than 0.01 and their survival by at most 5 points.
- **B2:** the paired difference's 95% interval holds 0 in all but 2 of the 18 pairs at most (1 miss is expected by
  chance).
- **B3:** over all 1,800 paired lives the mean difference is within 0.003.
- **B4:** the two engines rank the population alike: Spearman at least 0.9 on the same starts, under each draw of
  luck, and above the reference's own Spearman between the two draws of luck.

Also reported, with no criterion: how often single lives part, and whether the two rankings would move a search's
mean the same way (the cosine between CMA-ES's weighted steps).

**C. The cost** (describes): one core, and a whole generation on several processes.

**If A fails,** the kernel is wrong and is not used. **If B fails,** the kernel computes the model but something in
the differing library functions matters; it is not used for a search until that is understood.

## 5. Predictions

1. B1 to B4 all hold.
2. Single lives part: fewer than 90% of the paired lives agree to within 0.001 in fitness.
3. Most do not part far: at least 80% agree to within 0.01.
4. The two engines rank a population more alike (Spearman above 0.95) than one engine does under two draws of luck
   (below 0.9).

## 6. What I had seen before writing this

- A scratch prototype of the kernel, strict, against the reference under the C library's maths: identical, over 3,000
  ticks in the four trained worlds with four genomes, and over whole lives with two (two of the lives starved).
- 16 scratch lives of the default kernel beside the reference: most differed by 0.001–0.007 in fitness, one by 0.1
  (it survived in one engine and died in the other).
- The check's parts at the smoke test's size (a 2,000-tick day), where lives are too short to part.

So A's outcome is expected, the tolerances in B were chosen after the 16 lives, and the predictions are not blind.

## 7. What this does not show

- **Nothing about a GPU's speed or results.** `fastcheck --part gpu` and `--part speed --device cuda` are for a
  machine that has one. Consumer Nvidia GPUs do double-precision arithmetic at a small fraction of their
  single-precision rate, so the GPU may not beat the laptop's own CPU cores on this kernel. That is to be measured on
  the laptop, not assumed.
- **Nothing about single precision.** A single-precision kernel would suit a GPU far better and is a different
  instrument: positions near 5,000 R, an unbounded heading and small energy steps would need care. Not built.
- **Bit-for-bit agreement across machines.** The CPU kernel depends on the C library's four functions and on nothing
  else of the machine, so two machines with the same C library should agree; that is not checked here.

## 8. For the owner

1. **May the searches run on the compiled life?** Recommended if A and B hold.
2. **CPU or GPU on the laptop:** measure there first (`laptop.sh` runs the tests and both timings).
3. **The reliability run's design** (D45 C2), drafted separately as stage 8b.

## 9. Outcome (added 2026-11-24; D48, D49)

- **A holds:** 24 of 24 whole lives are the reference's in every number.
- **B1 fails as written.** Every pair's mean fitness is within 0.003, where 0.01 was allowed. One pair's survival is
  not within 5 points: champion 6402 under the spot, 20 of 100 on the reference and 28 on the compiled life.
- **B2, B3 and B4 hold:** no interval misses 0; over 1,800 lives the mean difference is −0.00002; the engines rank a
  population alike (Spearman 0.977 and 0.991, against 0.898 for the reference under two draws of luck).
- **Predictions:** 1 fails (B1); 2, 3 and 4 hold.
- **The follow-up on the one miss** (planned in D48 before it ran): the same cell and world on 600 fresh starts. Both
  engines have 152 lives survive. 164 lives survive in one engine and not the other, 82 each way. So the miss was the
  fall of lives that had parted, with no direction. My 5 points on survival were wrong for a pair whose lives part
  completely and survive one time in four; B1 stays recorded as failed.
- **C:** 11.7 times faster on one core (3.82 against 0.33 microseconds a cell-tick). A stage 8 generation takes 4.5 s
  on 8 processes here; the pods took 83–111 s on 16 vCPUs.
- **Still not shown:** anything on a GPU.
