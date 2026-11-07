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

## 10. What would change this document

The owner's answers, as dated notes before the first weight. The outcome as a dated note after the judge. Nothing else.
