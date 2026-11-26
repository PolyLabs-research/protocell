# Plan: a single-precision life for the GPU

**Written:** 2026-11-26, after the owner's decision D64 (item 4), before the check in §4 ran.

## 1. Why

- **The double-precision engine runs on a GPU and gains nothing there** (D54). On the owner's laptop (an NVIDIA RTX
  2000 Ada) 75 whole lives took 36 to 40 s on the GPU and 6 to 15 s on one of its CPU cores.
- **The likely reason:** consumer Nvidia GPUs do double-precision arithmetic at a small fraction of their
  single-precision rate, and nearly all of a life's arithmetic was double.
- **What a single-precision engine would buy is not known.** It is measured on the laptop, after this check.

## 2. What is built

`protocell/fast32.py`, with its GPU form in `protocell/fast32_cuda.py`: the compiled life of `protocell/fast.py`
with most of its arithmetic in single precision.

- **Double:** the cell's place (up to 5,000 R from the pool's centre), its heading (it grows without bound), the
  reserve, the damage, the light's source, and the sums the outcome is made of. The place relative to the source and
  the heading reduced to one turn are worked out in double and then rounded. About 25 operations a tick.
- **Single:** the light at each node, the senses, the network's step, the cilia's pull, the light soaked.
- **The same formulas as the reference,** with two rewritten where the arithmetic is the same: the falloff takes the
  squared distance (no square root then a square), and a division by a time constant is a multiplication by its
  reciprocal.
- **Specialised to the cell every stage uses** (16 wall nodes, 8 core neurons), so that a compiler can keep a life's
  state in registers. Anything else is refused.
- **The luck is the reference's:** a start's track is `protocell.fast`'s, its noise rounded to single precision.
- **The searches are untouched:** `fast.Mapper(precision="single")` and `fast.CudaMapper(precision="single")` send
  them the single-precision life's jobs.
- **Not the double engine's bits, and not meant to be:** single precision moves a last digit at every step, and a
  life is chaotic, so single lives part from the reference's sooner than the double engine's do.

## 3. What was seen before this plan (scratch runs here, not results)

- Over a life's first 400 ticks, in six worlds, positions stay within 0.0003 R of the double engine's and fitness
  within 1e-10.
- Over 30 whole lives each of two cells in two worlds, the mean fitness differs from the double engine's by −0.003 to
  +0.002, within one standard error each time; 20% to 73% of lives agree within 0.001.
- Its GPU code compiles here (NVIDIA's compiler runs without a device) with 127 of about 2,600 instructions on double
  precision, most of them loads, stores and conversions.

## 4. The check (`experiments/fastcheck.py --precision single`), and what it must show

**Part agree,** on this machine, on the CPU: part B of the double engine's check (D47, D48) with the single-precision
life in place of the double one, on the same starts and the same luck (seeds 50 to 53), so the three engines can be
set side by side: three cells (champions 8102, 6402 and 8105) on 100 starts in each of the six worlds a stage 8 run
meets, 1,800 paired lives; and run 8102's last population ranked as a search ranks it, under two draws of luck.

*Criteria* (B's, with the survival tolerance replaced as D49 taught):
- **S1:** in every cell-and-world pair the two engines' mean fitness differ by less than 0.01.
- **S2:** the paired difference's 95% interval holds 0 in all but 2 of the 18 pairs at most.
- **S3:** over all 1,800 paired lives the mean difference is within 0.003.
- **S4:** the engines rank a population alike: Spearman at least 0.9 under each draw of luck, and above the reference's
  own between the two draws.
- **S5:** the lives that survive in one engine only split with no direction: a two-sided sign test above 0.05, over
  all 1,800.

*Predictions:*
1. S1 to S5 all hold.
2. Single-precision lives part from the reference sooner than the double engine's: fewer than 74% of the paired lives
   (the double engine's share, D48 A.4) agree to within 0.001.
3. Most do not part far: at least 80% agree to within 0.01.
4. The engines rank a population more alike (Spearman above 0.95) than the reference does under two draws of luck
   (below 0.9).

**If S1 to S5 hold,** the single-precision life may be used for searches on the owner's word. **If one fails,** it is
not used until the failure is understood.

**Parts gpu and speed,** on the laptop (they describe; no criterion): the GPU's single-precision kernel beside the CPU's,
then a generation timed on the GPU, beside the laptop's 15.7 s on 20 processes. `python laptop.py` runs them.

## 5. What this does not show

- **Its speed.** Only the laptop can measure it.
- **That the GPU's single-precision kernel gives the CPU's outcomes.** Its library functions and fused multiply-adds
  differ again; part gpu compares them on the laptop.
- **Agreement across machines,** for the same reason as the double engine's.

## 6. Outcome of part agree (2026-11-26)

Ran from `a8792eb` on this machine, one process, 37 minutes; data in `docs/data/fast/agree-single/`.

- **S1 holds:** every cell-and-world pair's mean fitness within 0.006 of the reference's (0.01 allowed).
- **S2 holds:** no pair's interval misses 0.
- **S3 holds:** over 1,800 paired lives the mean difference is +0.0004 [−0.0008, +0.0016].
- **S4 holds:** the engines rank run 8102's last population alike (Spearman 0.979 and 0.964, against 0.898 for the
  reference under two draws of luck). The step a search would take agrees 0.916 and 0.912.
- **S5 holds:** 17 lives survive in the reference only and 20 in the single-precision life only (sign test p = 0.74).
- **Lives part sooner than the double engine's:** 61% of paired lives agree within 0.001 (the double engine 74%), 89%
  within 0.01 (92%).
- **All four predictions hold.**
- **So the single-precision life may be used for searches on the owner's word** (§4). Parts gpu and speed, on the
  laptop, are next.
