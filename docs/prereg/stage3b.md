# Preregistration draft: stage 3b — does comparing over time evolve, and where does it live?

**Written:** 2026-11-02, before any of it is built (`docs/decisions.md` D10). Stage 3a found a world where comparing
over time pays: with the cell translucent, the spatial reflex B2r scores 0.317 and survives a third of its starts,
while B5, which remembers one number, scores 0.709 and survives them all. Stage 3b evolves the cell in that world and
asks the plan's stage 3 question: does comparing over time evolve, and which parts carry it? The open points for the
owner are in §10.

## 1. The question

- **Q1, does evolution find comparison over time?** An evolved champion finds it if, on starts it never saw, its
  fitness exceeds B2r's by at least half the gap between B2r and B5. That gap is 0.39 on stage 3a's starts and is
  measured again on the test starts.
- **Q2, where does it live?** The removals of §6, each on each champion.
- **Q3, does it reach the bar?** Within δ of B5, δ = half B5's headroom: 0.021 / 2 ≈ 0.011. Reported. As in stage 1,
  the bar is near the ceiling.

## 2. The world, the cell, the bars

- **The world:** stage 3a's world exactly (`docs/prereg/stage3.md`; `experiments.stage3.configure()`): the cave's day
  configuration with the cell translucent and the falloff 600 R.
- **The cell:** stage 1's, in both spoke modes. τ ranges from 1 s to an hour.
- **The bars:**
  - B5 at τₘ = 30 s, the time constant stage 3a chose.
  - B2r at k = 100, the cell with no memory.
  - The still cell at the best fixed point, the ceiling's reference.
  - All three are scored again on stage 3b's own test starts.

## 3. Evolution

**Stage 1's algorithm unchanged** (`docs/prereg/stage1.md` §4; `protocell/evolve.py`):
- 96 genomes, 4 elites, parents drawn from the best 24;
- mutation sd 2% of each range;
- 8 fresh training starts a generation, with shared noise;
- **100 generations**;
- the champion chosen on 24 validation starts, every 10 generations.

Stage 3a's random genomes found almost nothing (none of 2,000 matched B5, the best scored 0.24), so evolution starts
lower than in stage 1. The pilot decides whether 100 generations are enough (§5).

## 4. Runs and seeds

- **The pilot:** one run per spoke mode, seeds 1101 (uniform) and 1102 (fourier1). Its outcome is recorded before the
  confirmatory runs. An amendment to the generations, the population or σ is allowed after it, with its reason.
- **The confirmatory runs:** three per mode, seeds 2101–2103 (uniform) and 3101–3103 (fourier1).
- **Validation starts:** seed 10. **Test starts:** 100 at seed 11. **Bootstrap:** seed 12. All fresh.
- **Where:** RunPod CPU pods as in stage 1: the pilot on one pod, the confirmatory runs on three. The owner confirms
  each launch's cost. The test runs here.

## 5. The pilot's rule

The pilot climbs if its champion survives at least half the validation starts. If a champion falls short of that by
generation 100 while its validation fitness is still rising, the generations are extended for the confirmatory runs,
with the reason recorded.

## 6. The removals (each confirmatory champion, on the test starts)

| removal | what is done | what it tests |
|---|---|---|
| R0, blind | the sensory gain set to 0 | a control |
| R1, the ring's links cut | the weights between ring neighbours set to 0 | the ring |
| R3, the core removed | every spoke set to 0 | the core |
| R4, the core's recurrence removed | every core-to-core weight set to 0 | memory held in loops among the core neurons |
| **R5, the wall made fast (new)** | the wall's time constant set to 1 s | memory held in the wall neurons' slow decay |
| **R6, the core made fast (new)** | every core neuron's time constant set to 1 s | memory held in the core neurons' slow decay |
| H-drive, H-rec, H-ring | the core's drive, the core's recurrence or the ring's links held at their average (stage 1b) | what each part computes |

A neuron with a long time constant integrates its input over time with no recurrence at all. So memory could sit in
the slow decay of the wall or the core neurons rather than in the core's loops. R5 and R6 separate the two. A removal
breaks a champion if the interval of its fitness drop has its lower bound above δ.

## 7. The criteria

- **Q1:** a spoke mode finds comparison over time if at least 2 of its 3 champions do.
- **Q3:** a mode reaches the bar if at least 2 of its 3 champions are within δ of B5 (lower bound above −δ).
- **Q2:** a part is needed in a mode if removing it breaks at least 2 of the mode's 3 champions.

## 8. Predictions (written before the build)

1. **Evolution climbs** in the fourier1 mode: the pilot champion survives most validation starts.
2. **The uniform mode does not find comparison over time.** A uniform-spoke cell in an even light field has no front.
   Every wall node is identical and receives nearly the same light, so its pulls tend to cancel, and it cannot hold a
   straight course to run on. **The fourier1 mode does find it** (Q1 in at least 2 of 3).
3. **Q3:** neither mode reaches B5 within δ. B5 is thrifty and near the ceiling.
4. **Q2 in the fourier1 mode:**
   - R0 breaks every champion.
   - Holding the core's drive at its average breaks every champion: it switches the wall.
   - Comparison over time lives in slow decay rather than in loops: R6 (the core made fast) breaks at least 2 of 3,
     and R4 (the recurrence removed) breaks fewer than R6.
5. **Effort per unit light:** the champions spend more than B5 (0.06). B5 waits most of the time and is hard to match
   on thrift.

## 9. Decision table

| result | what follows |
|---|---|
| the pilot does not climb in either mode | an amendment (generations, population or σ) with its reason; the pilot again on fresh seeds |
| a mode finds comparison over time | its removals read for where the memory lives; the owner's call on the next stage (damage, or changing light) |
| neither mode finds it | recorded; the owner's call whether evolution runs longer or the cell is given more to work with |

## 10. Open for the owner

1. **The generations:** 100 as stage 1, extendable after the pilot (recommended), or 150 from the start, since random
   wiring starts lower here.
2. **The new removals R5 and R6** (recommended). They are what can tell loops from slow decay.
3. **RunPod** as in stage 1, with each launch's cost confirmed: the pilot about $2 and the confirmatory runs about $6
   at stage 1's rates.

## 11. What would be built

- R5 and R6 as removals.
- The holds of stage 1b in stage 3b's test.
- `experiments/stage3b.py`: stage 1's runner pointed at stage 3a's world and bars, with stage 3b's seeds.
- Tests for each.

## 12. What would change this document

The owner's answers, as dated notes before the build. The pilot's outcome and any amendment, as dated notes before
the confirmatory runs. After those, nothing.
