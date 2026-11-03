# Preregistration draft: stage 4b — evolution in a world with room above every simple rule

**Written:** 2026-11-03, after stage 4a's checks passed (`docs/decisions.md` D17), before anything is built.

## 1. The question

The owner's hypothesis is that behaviour emerges from the interaction of parts. Its strong sense is that interacting
parts do better than every simple mechanism. In every world before stage 4a, a simple rule sat within 2–3% of the
ceiling, so the strong sense could not show (D11). Stage 4a's world leaves room:
- the best simple rule, B8, is 0.118 below the ceiling, 22% of the room above sitting still;
- perfect reading of the light's direction recovers 73% of that.

**Stage 4b asks three things:**
- **Q1, the strong sense:** does evolution find a cell that beats every simple rule here?
- **Q2:** which of its parts does it need?
- **Q3:** how does it manage? Does it read the light's direction, compare over time, or both? Stage 3c's instruments
  answer this.

## 2. The world, the cell, the bar

- **The world:** stage 4a's, unchanged (`docs/prereg/stage4.md` §2). It is stage 3's translucent pool, with the mouth
  sweeping along the edge through the day and photosynthesis at 0.55 of the cave's gain.
- **The cell:** as in stage 3b, in both spoke modes (uniform, 103 genes; fourier1, 135).
- **The bar:** B8 with τ = 10 s, chosen by stage 4a and scoring 0.576 there.
  - Beside it on the test starts: B5 (τ = 3 s), B6, the ceiling and B0.

## 3. Evolution

- **The algorithm:** stage 1's and stage 3b's, unchanged.
  - 96 genomes, 4 elites, parents drawn from the best 24, mutation σ 0.02 of each range, no crossover.
  - 8 fresh training starts a generation with shared noise.
  - Validation every 10 generations on the top 3, in stage 4a's world.
  - Checkpoints, and resumes bit for bit.
- **A path (recommended; §10 1):**
  - Over generations 1–50 the training world eases into stage 4a's. The shading fades from the cave's 0.3 to none, as
    stage 3b's amendment A1. At the same time the photosynthetic gain falls from the cave's to 0.55 of it, both in
    straight lines.
  - Generations 51–150 train in stage 4a's world.
  - The champion is chosen from generation 51 on, by validation in stage 4a's world.
  - The reason: stage 4a found the best of 2,000 random genomes no better than sitting still (D17). Stage 3b's pilot
    collapsed onto still cells in a landscape like that, and amendment A1's fade gave every one of its runs a working
    cell to start from.
- **150 generations** (recommended), against stage 3b's 100: 50 easing in and 100 in the world itself. Stage 3b's
  champions came from generations 90 and 100, late in their runs.

## 4. Runs and seeds

- **Run seeds, fresh:**
  - Pilot: one run per mode, 1301 (uniform) and 1302 (fourier1).
  - Confirmatory: three per mode, 2301–2303 and 3301–3303.
- **Validation:** 24 starts at seed 20.
- **The test:** 100 starts at seed 21.
- **Bootstrap:** seed 22.

## 5. The pilot's rule

The pilot's champion must survive at least half of the validation starts in stage 4a's world, as in stage 3b. If
neither mode's pilot does, an amendment comes before any confirmatory run (§9).

## 6. The test (each confirmatory champion, on the test starts)

1. **Against the bar:** each champion, and B8, B5, B6, the ceiling and B0, start by start with shared noise.
2. **The removals,** stage 3b's, without re-evolving:
   - R0, blind;
   - R1, the ring's links cut;
   - R3, the core removed;
   - R4, the core's recurrence removed;
   - R5, the wall made fast;
   - R6, the core made fast.
3. **The holds:** stage 1b's holds of the core's drive, the core's recurrence and the ring's links at their averages.
4. **How it manages,** with stage 3c's instruments (`docs/prereg/stage3c.md` §3):
   - The goggles: each champion with the direction removed (k = 0) and mirrored (k = −1). Its runs' onset bias is read
     as in stage 3c.
   - The flat pool: each champion held in place in even light, stepped up and down at 0.3 and 1, giving stage 3c's T.

## 7. The criteria

δ = 0.012, a tenth of stage 4a's headroom above the bar.

- **Q1, it beats every simple rule.**
  - A champion beats the bar if its fitness less B8's has its 95% interval above 0.
  - A spoke mode beats the bar if at least 2 of its 3 confirmatory champions do.
  - Reported for each champion: the share of the headroom it claims, (champion − B8)/(ceiling − B8).
- **Q2, a part is needed** in a mode if its removal or hold drops the fitness of at least 2 of the 3 champions by more
  than δ (interval above δ).
- **Q3, how a champion manages:**
  - **It reads the direction** if removing the direction drops its fitness by more than δ (interval) and its onset bias
    turns negative with the direction mirrored (interval below 0). These are stage 3c's C1 and C2 on its own.
  - **It compares over time** if it meets stage 3c's C5 in the flat pool.

## 8. Predictions (written before the build)

1. **The pilot climbs** in at least one mode under the path.
2. **Q1 fails in both modes: no champion beats B8.** Stage 3b's search reached 0.48 against B5's 0.715 in an easier
   world, and nothing here makes the search stronger.
3. **The best champion scores below B8,** so it claims none of the headroom, as every evolved cell has scored below
   the best simple rule so far.
4. **Q3: the champions that work read the direction, and none compares over time,** as stage 3c found for stage 3b's
   champions.
5. **Q2: the core and the ring's links are needed** in both modes, as in stage 3b.

## 9. Decision table

| result | what follows |
|---|---|
| the pilot climbs in neither mode | an amendment to the path or the generations, with its reason; the pilot again on fresh seeds |
| Q1 holds in a mode | the strong sense shown in this world; the champions' parts and mechanism read (Q2, Q3); the owner's call on what follows |
| Q1 fails in both modes | recorded; the owner's call: a stronger search (more generations, or CMA-ES, deferred in D6), or another question |

## 10. Open for the owner

1. **The path:** the shading and the gain easing in together over generations 1–50 (recommended).
   - Or no path, which stage 4a's numbers suggest would collapse onto still cells as stage 3b's first pilot did.
   - Or the two eased in one after the other.
2. **The generations:** 150 (recommended), or 100 as in stage 3b.
3. **The criteria:** Q1's interval above 0, and δ = 0.012 (recommended).
4. **RunPod, as in stages 1 and 3b,** with each launch's cost confirmed before it starts.
   - The pods: cpu5c with 32 vCPUs at $1.12 an hour, each running one uniform and one fourier1 run side by side.
     150 generations take about 2.4 hours.
   - The pilot pod: about $2.70, at most $3.90 with a 3.5-hour cap.
   - The three confirmatory pods: about $8.10, at most $11.80.
   - The balance today is $23.59. The chess project's pods are spending $2.03 an hour from it.

**The owner's answers (2026-11-03, before the build).** "agree, go":
- the path, the shading and the gain easing in together over generations 1–50;
- 150 generations;
- the criteria as in §7;
- RunPod, with the pilot pod confirmed at $1.12 an hour, a 3.5-hour cap and at most $3.90.

The confirmatory pods' cost is confirmed after the pilot's outcome.

## 11. What would be built

- **`experiments/stage4b.py`:**
  - Stage 3b's runner pointed at stage 4a's world, with the path and stage 4b's seeds, and validation in stage 4a's
    world.
  - The test with the bar, the removals, the holds, the goggles and the flat pool.
- **`cloud/`:** the scripts take `EXPERIMENT=stage4b` as they are.
- **Tests,** including that the path ends at stage 4a's world and that the champion comes from generation 51 on.

## 12. What would change this document

The owner's answers, as dated notes before the build. The pilot's outcome and any amendment, as dated notes before
the confirmatory runs. After those, nothing.
