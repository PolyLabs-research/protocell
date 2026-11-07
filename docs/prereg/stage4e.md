# Preregistration draft: stage 4e — writing the cell by hand

**Written:** 2026-11-07, after stage 4d (`docs/decisions.md` D23, D24), before any weight is written. The owner: "Yes draft
away".

## 1. The question

D22 found that the evolved cells die in stage 4a's world because they find about half the light B8 finds. D23 left open
why no search does better:
- **The cell is the limit:** this network cannot do what B8 does.
- **The searches are the limit:** it can, but neither evolving on survival nor fitting B8's beats finds how.

Stage 4e asks the question directly: **can a cell written by hand, weight by weight, do B8's job in stage 4a's world?**

A success settles it: the cell can, and the searches are what fail. A failure is weaker evidence, since the limit may be
the writer's design rather than the cell. A failure is still useful, because the written notebook names the part that
blocked each attempt.

## 2. Background

- **The precedent:** a blog post from MIT CSAIL, "Weight-Space Programming" (Takehi, Teoh, Zhang, Khattab, about 2
  November 2026; not peer-reviewed). A frontier language model wrote and repaired the weights of small networks by
  reasoning, with no gradient descent.
  - It wrote a MinAtar Breakout policy of about 17,000 weights in one reply, scoring 517 against 25 for PPO after 500
    million steps.
  - Its harder tasks needed a budget of about 50 test runs.
  - Its own limit: "editing weights could remove an obstacle that hid an ability, but it could not add an ability the
    model lacked".
- **How this cell differs:** it is far smaller, 103 or 135 numbers against 17,000. But it is recurrent and runs in
  continuous time, which the post did not cover.
- **Three constraints of the cell's wiring** (`protocell/cell.py`, `protocell/sim.py`), any of which might block B8:
  1. **Light enters only at the wall, and the wall's outputs are the beats.** The core learns of the light only through
     the beats, so a cell at rest with no beats has a core that knows nothing of the light.
  2. **All 16 wall neurons share one time constant.** The wall alone cannot compare the light now with the light a
     moment ago; a rise must be found in the core, back to constraint 1.
  3. **There is no gain control.** Inputs are the sensory gain times the light, into sigmoids that saturate, while the
     light in stage 4a's world spans about 0.01 to 10.

## 3. What is written

- **One cell per spoke mode, fourier1 first** (§9, item 2). It is a genome within the cell's ranges:
  - weights and biases in [-8, 8];
  - time constants from 1 to 3,600 s;
  - the sensory gain in [0, 20];
  - the cilium angle, which is free.
- **The wiring is the cell's own:** nothing added, nothing removed.
- **Written from scratch:** no evolved or fitted genome is a starting point, though every past result may inform the
  design.

## 4. How it is written

- **A notebook** (`docs/data/stage4e/<mode>/notebook.md`). Each design gets a number, its parameters by name, and a few
  lines saying what it should do and why, written **before** its check runs. The check's numbers follow, then what was
  learnt.
- **World checks, the budget: at most 50 per mode** (§9, item 1).
  - A check runs one design closed loop in stage 4a's world on some or all of stage 4b's 24 validation starts (seed 20),
    with shared noise. It may record the run's trace.
  - The tool counts each check, writes its design and results down, and refuses the 51st.
- **Open-loop probes, unlimited but logged** (§9, item 3). A probe runs the network alone on inputs the writer chooses,
  such as a step in the light. It is a calculator for one design.
- **No automated search.** No loop may score many candidate weight sets and keep the best, whether by probes or by checks.
  Every design is written deliberately, one at a time.
- **Submission:** the writer submits one design per mode for the judge. It is chosen on its checks, and the notebook says
  why.

## 5. The judge

- **The runs:** the submitted cell, B8 (τ = 10 s) and B0, closed loop in stage 4a's world on fresh starts 1–100 at seed 27,
  with shared noise.
- **The measure:** the share of the gap from B0 to B8 the cell closes, on mean fitness, with a 95% bootstrap interval
  (seed 28). This is stage 4d's measure on new starts.
- **Also reported:** survival, the light per daylight tick lived, the beat by day and by night (the thrift probe's
  measures), and the number of checks used.

## 6. The verdict, per mode

| share of the gap closed | verdict | what follows |
|---|---|---|
| at least 0.9 | **carries B8** | the cell can find light as B8 does; the searches are what fail. Next, evolution starting from this cell, with the strong sense as its question |
| 0.5 to 0.9 | **partly** | the owner's call |
| below 0.5 | **does not** | the notebook names what blocked it; changing the cell (D23 C2) is the likely next step |

If the written cell beats B8, with the interval above a share of 1, that is reported too. It would show that the cell's
parts *can* beat the best simple rule, by design. It would not show that such a cell emerges, which is the owner's
hypothesis.

## 7. Predictions (written before any weight)

1. **The fourier1 cell closes at least half the gap** ("partly" or better). With a front it can run straight ahead while
   the light rises, as B5 does, and B5 closes about nine tenths of the gap in stage 4a's checks.
2. **It does not beat B8.**
3. **It beats more by day than B8** (B8: 0.098 on stage 4d's judge). Constraint 1 makes it beat a little all day just to
   sense the light.
4. **If the uniform mode is written (§9, item 2), it closes less of the gap than the fourier1 cell.** Without a front it
   must aim from the light across its body alone, which constraint 3 makes hard.

## 8. Compute and risk

- **Everything runs as one process on one core,** with no worker pool. A check on 24 starts takes about half a minute;
  the judge takes about five minutes.
- **The host:** sustained multi-core runs trip this machine's thermal limit (D23 A1). On 2026-11-05 one busy core held the
  CPU at about 65°C, with brief spikes into the 90s, against 98°C with four or more. The heat trace logs alongside every
  check.
- **Cost:** none. Nothing on RunPod.

## 9. Open for the owner

1. **The budget: 50 world checks per mode** (recommended, as the precedent's 50 test runs). Fewer would test the design
   more than the cell; more would drift toward search by hand.
2. **Fourier1 first, then uniform** (recommended). Uniform is the harder test of constraint 3, and it is worth writing
   whatever fourier1's verdict, so the two can be compared.
3. **Unlimited logged open-loop probes, with no automated search** (recommended). They are how a writer checks that a
   part does what it should before spending a world check on the whole.

**The owner's answers (2026-11-07, before any weight):** "1. ok 50, 2. agree 3. agree. 4. go".
- **Budget:** 50 world checks per mode.
- **Order:** fourier1 first, then uniform, whatever fourier1's verdict.
- **Probes:** unlimited and logged, with no automated search.

The tool is `experiments/stage4e.py`. Its commands are `genome`, `probe`, `check`, `note` and `judge`. It enforces the
budget, writes each design's reason to the notebook before its check runs, and refuses a check from a tree with tracked
changes. The judge runs once per mode.

**The outcome (2026-11-07).**

The data are in `docs/data/stage4e/`: each mode's notebook, designs, logged probes, checks with their traces, and judge.
- **How:** everything ran on this machine as one process, from clean trees with warnings as errors. The tool was committed
  before each check.
- **What was used:**
  - **Fourier1:** 11 designs written (17 files with calibration variants), 170 probes, 5 world checks of 50.
  - **Uniform:** 2 designs (4 files), 34 probes, 1 check of 50.

**Neither written cell does B8's job.** On the judge's 100 fresh starts (seed 27):

| | fourier1 cell (design 4) | uniform cell (design 2) | B8 | B0 |
|---|---|---|---|---|
| fitness | 0.152 | 0.149 | 0.554 | 0.156 |
| survival | 0% | 0% | 93% | 0% |
| light per daylight tick lived | 0.103 | 0.100 | 0.589 | 0.101 |
| beat by day / by night | 0.048 / 0.041 | 0.038 / 0.036 | 0.096 / 0 | 0 / 0 |
| share of the gap closed (95% interval) | -0.010 (-0.020, 0.001) | -0.018 (-0.021, -0.015) | | |
| verdict | does not | does not | | |

**The world checks** (24 validation starts, all 2,400–9,300 R from the mouth, where B8 survives 23 of 24):

| check | design | what it tested | fitness | reached the soak region |
|---|---|---|---|---|
| fourier1 1 | 4 | B5 in the cell: adaptation, a fast/slow comparator, a run switch, a creep | 0.144 | 21% |
| fourier1 2 | 8 | a symmetric dither whose phases weigh the light (lock-in) | 0.139 | 12% |
| fourier1 3, 4 | 9, 10 | design 4 at gain 8 and 20, not recentred (confounded) | 0.137, 0.137 | 12%, 8% |
| fourier1 5 | 11 | design 4 at gain 8, recentred on the far field | 0.136 | 12% |
| uniform 1 | u2 | a winner-take-all ring bump released in bursts | 0.140 | 12% |

Every check sat at B0's level (0.148 on these starts).

**What blocked it, from the notebooks:**
1. **The cell senses only through its beats** (constraint 1).
   - Any motor act changes the sum the core reads by about 1–5 units. A far-field move gains about 0.05 of light signal,
     so the move swamps it 20–100 times over.
   - A CTRNN neuron forgets exponentially, so no neuron holds the light across a move.
   - Run switches that read their own effects oscillate (designs 1, 5).
   - In the world, a design that showed B5's behaviour in probes moved a lot without direction (check 5: median net
     displacement 1,560 R, reached 3 of 24).
   - First-harmonic spokes cannot isolate the side nodes a front-back drive leaves alone.
2. **The cell has no gain control** (constraint 3).
   - To use the bright light this economy demands (light 3–10), three adaptation neurons cap the gain near 2.5.
   - At that gain, far-field light (0.04–0.14) moves the wall's input by under a tenth of a sigmoid's width: nearly the
     same as night (measured sums 3.25 at night, 3.4–3.9 in the far field).
   - Gain 8 separates night from far field (3.25 against 3.92–4.75) but saturates the wall above light ~3.4 (beat 1.0 at
     light 5).
3. **Eight core neurons are too few** for B6's read-then-run with memory kept clean. It needs readers, drivers, a timer,
   adaptation and a dark gate: about 10.
4. **The symmetric dither (design 8).** It gets round constraint 1 (the run's leak is the same in both phases) and the
   information is there (far-field signal to noise ~2 per cycle). But the gain from light to motion is about 100 times
   short; in the world the net displacement was 7–310 R over whole lives. My estimate of its mid-field drift was
   optimistic.
5. **Uniform.** Direction can come only from the ring. In the mid field the light across the body is about 16 times below
   the sensors' noise per node per tick, so a ring winner-take-all picks noise winners. The pull in probes pointed the
   right way but was ~0.0005 v_max at ten times the real contrast.

**The predictions:**

| prediction | outcome |
|---|---|
| 1. the fourier1 cell closes at least half the gap | ✗: -0.010 |
| 2. it does not beat B8 | ✓ |
| 3. it beats more by day than B8 (0.096) | ✗: 0.048. It beats at night instead (0.041 against B8's 0), the sensing cost constraint 1 predicts, but it runs far less by day |
| 4. the uniform cell closes less of the gap than the fourier1 cell | ✓ narrowly: -0.018 against -0.010, both at B0's level |

**By §6:** "does not" in both modes. The notebooks name what blocked each attempt.

**Caveats:**
- A failure is weaker evidence than a success would have been: the limit may be the writer.
- Six of the hundred checks were used. The notebooks argue that further variants of these mechanisms meet the same walls,
  but that is an argument, not a test.
- Several of my calibrations missed and were redone in probes. One test (checks 3–4) was confounded, and one estimate (the
  dither's drift) was optimistic.
- The evolved cells did better than these written ones. Stage 3b's uniform champion scored 0.216 in stage 4a's checks and
  reached the soak region on 42% of starts, against B0's level here.

## 10. What would change this document

The owner's answers, as dated notes before the first weight. The outcome as a dated note after the judge. Nothing else.
