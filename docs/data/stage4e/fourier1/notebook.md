
**Learnt (2026-11-07 14:41 UTC):** Design 1, probes only, no world check. (1) At light 5 the adaptation loop rings: four identical steep neurons (spokes in 8, tau 20) correct by about 3x the error each tick, so the wall bursts every ~40 ticks. Gentler spokes would leave them half on in the dark and press the wall down where it should sense. Slow but steep is the way out (tau ~100). (2) At light 1.4 the run switch drives itself: the run's beats leak into the sum F and SL read, and F follows the swings faster than SL. A calculation shows the leak changes sign if the wall's resting level shifts by 0.3, which no adaptation here can hold. Constraint 1 (the core sees light only through the beats) in action: this cell cannot compare light while it runs. Next: sense only between runs. The cell creeps forward at rest (the creep supplies the motion B5 compares across), and a rise fires a timed burst. (3) At light 0-0.5, F and SL sat in their low tails: nearly blind in the far field, so the resting level must be set for low light.

**Learnt (2026-11-07 16:23 UTC):** Design 2 and stage A of design 3, probes only. (1) Slow, steep adaptation (tau 100) is stable, and self-excitation (3.5) pins the wall's resting sum within 5.65-7.14 from light 1.4 to 9. (2) Below light ~1 nothing pins it, because the adaptation is not engaged and the wall rides the light: the sum runs from 3.3 (dark) to 4.8 (0.5). (3) Constraint 3 in numbers: the adaptation cancels at most 24 units (3 neurons x 8), so to reach light 10 the gain is at most ~2.5. Far-field light of 0.14 then moves the wall's input by 0.35, against a sigmoid about 4 units wide: for this cell the far field is nearly as dark as night. (4) Design 2's comparator (F, SL at bias -4) was set for the far field and saturated by light 1.4 (F - SL only 0.01 under a real ramp): its sensitive band was narrower than the drift. Next (design 3): halve F and SL's spoke weights so one bias covers both bands, at half the slope.

**Learnt (2026-11-07 16:28 UTC):** Design 3, probes only. Halving F and SL's weights kept them sensitive in name but deaf in fact: no noise-triggered bursts anywhere, no response to rises at the rate the creep makes, bursts only for burst-rate rises in mid light. A cell that bursts only when it is already going up never starts: chicken and egg. B5's exploring runs come from noise near the threshold, so the comparator needs its full slope. My error, not the cell's. Next (design 4): full weights again, with the pinned range (sum 3.3-7.1) centred on F's curve (bias -5.2).

### Check 1: `d04.json` (f19b80722827), starts 1-24

**Why, written before it ran:** Design 2's full-weight comparator (F and SL read 8 - 8 cos theta), with design 3's self-pinned adaptation (S1-S3 self 3.5) holding the front-blind sum between ~3.3 (dark) and ~7.1 (light 9). F and SL's bias -5.2 centres that whole span on their curve, so the comparator keeps its full slope from far field to bright light. Expected: noise near R's threshold fires exploring bursts at rest (as B5's runs), a burst that raised the light leaves F above SL and fires the next, and falling light quiets it; parking in bright light (H).

| | this design | B8 | B0 |
|---|---|---|---|
| fitness | 0.144 | 0.567 | 0.148 |
| survival | 0% | 96% | 0% |
| light per daylight tick | 0.116 | 0.606 | 0.115 |
| beat by day / night | 0.049 / 0.041 | 0.100 / 0 | 0 / 0 |
| reached the soak region | 21% | 100% | 12% |

Share of the gap from B0 to B8 on these starts: -0.01. Check 1 of 50; 27 s; code 14ea004.

**Learnt (2026-11-07 18:04 UTC):** Check 1 (design 4): 0.144, B0's level (0.148), against B8's 0.567. Reached the soak region on 5 of 24 starts, all among the nearer ones (up to ~4,900 R), none surviving. Every validation start is far field (2,400-9,300 R from the mouth), where B8 reaches all 24. Design 4 was deaf there at rest (probes: no bursts at light 0.07-0.14). The cell's hardest limit: with gain capped near 2.5 by the adaptation's range, night (wall sum 3.25) and far-field light (0.04-0.14: 3.4-3.9) look nearly alike to it, where B8 tells them apart exactly at 0.01. Next (design 5): a near-critical dark detector D on the wall sum, set between night and light 0.04, replaces the bright-light gate. R and Q become a pacemaker firing exploring bursts while D says there is light (B5's runs come from noise; here they are built in). F - SL speeds the bursts while light rises and stops them while it falls.

**Learnt (2026-11-07 18:08 UTC):** Design 5 (probes only). R's leaky resting output (0.1-0.3) tilts the wall, the tilt changes the sum F reads, and F feeds back to R: a small 12-tick oscillation instead of bursts, with D hovering half-on in the swings. Constraint 1 at R's resting level, not only in bursts. The sign problem: to first order a small tilt is cancelled by a drive offset of +4 (front nodes weigh little in the front-blind sum, back nodes a lot), a full burst by -1.4. One neuron's drive is one pattern, so no single offset cancels both. Worse, the burst's leak into the sum (about 1-5 units) is 20-100 times the far-field light signal a burst produces (~0.05), and it moves by about 2 units per 0.3 change in the wall's resting level, so no fixed weighting can null it. First-harmonic spokes cannot isolate the side nodes a front-back drive leaves alone. Next (design 6): R as a clean switch with large hysteresis (self 7, off-output ~0.025), so its resting state cannot drive the loop. The pacemaker's timing comes from Q's decay near its floor, where small comparator shifts move the timing a lot.

**Learnt (2026-11-07 18:16 UTC):** Design 6 (probes only) missed calibration again: removing R's tilt raised the night sum to ~3.64, so D sat on at night; the pacemaker did not fire at low light. The bigger lesson is from calculation, not probes. A burst floods the wall's sum by ~1-5 units, against far-field light signals of ~0.05 per burst. Every neuron that integrates the sum takes in the flood, and a CTRNN neuron forgets exponentially, so nothing remembers the light across a burst to the precision the far field needs. B5's compare-across-a-move is out of reach there, and all 24 validation starts are far field. A B6-style reader-and-driver design keeps memory clean only with separate readers, drivers, timer, adaptation and dark gate: about 10 neurons, the cell has 8. Next (design 7): use constraint 1 instead of fighting it. A symmetric dither, forward and back with equal drive, contaminates the wall's uniform sum identically in both phases (the ring's symmetry), so only the light difference between the two positions differs. Two sampler neurons, each gated into its sensitive range by the phase, read the sum in one phase each and feed the timer, so a brighter forward phase lasts longer and a darker one shorter: the dither drifts up the gradient. Calculation: with Q's drive equal to the sum of its two thresholds, the dither stays symmetric in steady light at any level.

**Learnt (2026-11-07 18:18 UTC):** Design 7 (probes only). The dither runs as designed: forward and back phases of ~13 ticks, no net drift in steady light (+0.004), cost 0.04-0.06 beat, from dark to light 9. But the gain from light to motion is ~100x short in the far field. One ~10 R excursion changes far-field light by ~0.0006. The information is there (per-cycle signal to noise ~2, since the uniform sum averages 16 nodes), but every link loses gain: the wall's slope at rest (~0.03), A's weight (2, held down by its bias range), A's slope (~0.09). The phase timing moves ~0.05%. Full gain needs ~200 R excursions, a shuttle of half the wall at ~0.8 all day (~0.35 beat, over 3x B8's spend). That is the trade this cell keeps hitting: B8 moves only when moving pays, because it remembers; this cell cannot remember across its own motion, so it must keep moving to sense. Next (design 8): readers at full gain (negative spokes, so their bias fits: A = sigmoid(-8 sum + 8 P + b), B gated by K - P), larger excursions (drive +-4, longer phases), aimed at the mid field. Then a world check with trace.

**Learnt (2026-11-07 18:59 UTC):** Designs 7-8 calibration (probes). Two causes of a lopsided dither: (1) a single sigmoid switch cannot be clean (with self 7 its on-state sags to ~0.83 near the flip); (2) cutting the readers from Q breaks the symmetry condition. Design 8 adds Pb = sigmoid(4 - 8 P) to push backward, in place of the tonic K, so the two phases sag as mirror images. The readers use negative spokes so their bias fits at full slope. Probes: in steady light the phases still differ by ~5% in sum and pull, but they balance (net drift per cycle ~0 at every level from dark to 9). Gradient climbing only shows closed loop: next, a world check with trace.

### Check 2: `d08.json` (197553273337), starts 1-24

**Why, written before it ran:** Design 7's dither made symmetric and given gain, aimed at the mid field. P is the phase switch (self 7, bias +3: on while Q < ~0.72, off once Q > ~0.90) and Pb its clean complement (sigmoid(4 - 8 P)). They push the wall +3 cos theta and -3 cos theta (P's and Pb's spokes), so the two phases sag alike as P's output does, mirror images. A and B read the uniform sum with negative spokes (-4), so their bias fits (-1.6), each lifted into range only in its own phase (A by +8 P, B by +8 Pb); a brighter phase makes its reader lower. Q (tau 12, bias 1.04) is driven by P (+1.06), A (+4) and B (-4). Phase lengths depend on how near Q's targets sit to P's thresholds (~0.5 in steady light), so a brighter forward phase (A lower) lasts longer and a darker backward phase (B higher) ends sooner: drift up the gradient. Q's drive from P equals the sum of P's thresholds in Q's units (-0.1 + 1.16), which keeps the phases equal in steady light; the readers' common level sets the phase length. S1-S3 adapt as before. Expected: steering in the mid field (~0.5 R/tick by calculation at 2,500 R), little in the far field.

| | this design | B8 | B0 |
|---|---|---|---|
| fitness | 0.139 | 0.567 | 0.148 |
| survival | 0% | 96% | 0% |
| light per daylight tick | 0.112 | 0.606 | 0.115 |
| beat by day / night | 0.040 / 0.039 | 0.100 / 0 | 0 / 0 |
| reached the soak region | 12% | 100% | 12% |

Share of the gap from B0 to B8 on these starts: -0.02. Check 2 of 50; 28 s; code 031d7ea.

**Learnt (2026-11-07 19:00 UTC):** Check 2 (design 8, the dither): 0.139, reached 12%, none survived. The trace shows why: over each life the net displacement was 7-310 R against a dither path of 3,500-17,000 R; distance to the mouth changed only because the mouth swept. The dither does not climb the gradient, even from 2,400 R, where my estimate said ~0.16-0.5 R/tick: my gain estimate was optimistic. Next: test the central claim in the world, not on paper. The economy demands bright light (I ~3-10), which caps the gain near 2.5, which blinds the far field. Design 4 with gain 8 and with gain 20 should find light more often but starve in bright light (the walls saturate and beat flat out). If so, the range trade-off is confirmed.

### Check 3: `d09.json` (0c35d6862a73), starts 1-24

**Why, written before it ran:** A test of the range trade-off, not a candidate: design 4 with the wall's gain raised from 2.5 to 8. The adaptation (24 units) then covers light only up to ~3.4; above that the walls saturate and beat flat out. Prediction: at gain 8 the far field moves the wall 3.2x as much, so the cell finds the soak region more often than design 4's 21%, but it starves in bright light (cost ~2x resting) and survival stays ~0. If so, the gain the far field needs is the gain bright light forbids.

| | this design | B8 | B0 |
|---|---|---|---|
| fitness | 0.137 | 0.567 | 0.148 |
| survival | 0% | 96% | 0% |
| light per daylight tick | 0.110 | 0.606 | 0.115 |
| beat by day / night | 0.065 / 0.041 | 0.100 / 0 | 0 / 0 |
| reached the soak region | 12% | 100% | 12% |

Share of the gap from B0 to B8 on these starts: -0.03. Check 3 of 50; 28 s; code 031d7ea.

### Check 4: `d10.json` (0ea8d5435868), starts 1-24

**Why, written before it ran:** A test of the range trade-off, not a candidate: design 4 with the wall's gain raised from 2.5 to 20. The adaptation (24 units) then covers light only up to ~1.4; above that the walls saturate and beat flat out. Prediction: at gain 20 the far field moves the wall 8.0x as much, so the cell finds the soak region more often than design 4's 21%, but it starves in bright light (cost ~2x resting) and survival stays ~0. If so, the gain the far field needs is the gain bright light forbids.

| | this design | B8 | B0 |
|---|---|---|---|
| fitness | 0.137 | 0.567 | 0.148 |
| survival | 0% | 96% | 0% |
| light per daylight tick | 0.107 | 0.606 | 0.115 |
| beat by day / night | 0.078 / 0.041 | 0.100 / 0 | 0 / 0 |
| reached the soak region | 8% | 100% | 12% |

Share of the gap from B0 to B8 on these starts: -0.03. Check 4 of 50; 28 s; code 031d7ea.

**Learnt (2026-11-07 19:02 UTC):** Checks 3-4 (design 4 at gain 8 and 20): 0.137 both, reached 12% and 8%, none survived. My prediction (more reach, starvation in bright light) failed on reach. The test was confounded: I raised the gain without recentring F and SL (set for gain 2.5's sums). Traces: higher gain made the cells move much more (median net displacement 1,430 and 1,994 R, against 164 for the dither) but not toward light: undirected bursts. Next: the fair version, design 4 recalibrated at gain 8 (F, SL and D-free comparator centred on the measured sums).

### Check 5: `d11.json` (76883961d597), starts 1-24

**Why, written before it ran:** The fair test of gain: design 4 at gain 8, recalibrated. Measured sums at gain 8: night 3.25, light 0.05 3.92, 0.14 4.75, 0.3 5.36, 0.5 5.68, 1.4 6.23, 3 8.68 (adaptation maxed), saturated by 5. F and SL now centre on the far-field band (bias -4.8), so B5's comparison has its full slope at light 0.05-0.5, and night sits well below it. H still parks the cell from about light 1.4 (driven by the adaptation), before the walls saturate above ~3.4. Prediction: noise-triggered exploring bursts and rising-light retriggering now work in the far field, so the cell finds the soak region more often than design 4's 21%; it can feed only where light is 1.4-3, parked, so survival stays low.

| | this design | B8 | B0 |
|---|---|---|---|
| fitness | 0.136 | 0.567 | 0.148 |
| survival | 0% | 96% | 0% |
| light per daylight tick | 0.108 | 0.606 | 0.115 |
| beat by day / night | 0.067 / 0.041 | 0.100 / 0 | 0 / 0 |
| reached the soak region | 12% | 100% | 12% |

Share of the gap from B0 to B8 on these starts: -0.03. Check 5 of 50; 27 s; code 031d7ea.

**Learnt (2026-11-07 19:08 UTC):** Check 5 (design 11, gain 8 recalibrated): 0.136, reached 3 of 24, none survived, median net displacement 1,560 R. The probes showed B5's far-field behaviour (exploring bursts 23-24%, more on rising light, few on falling), but it did not carry into the world. A probe's light does not change when the cell moves; the world's does. Each burst's own beats leak into the comparator ~20-100x more than the light it gained, so in closed loop the retrigger decisions are noise: plenty of motion, no direction. Constraint 1 confirmed in the world. Submission: design 4, the best on its checks (0.144, reached 21%; all eleven designs sat at B0's level, 0.136-0.148, against B8's 0.567). Five checks used of 50: the notebook's analysis says further variants of these mechanisms meet the same three walls, so more checks would test variations, not the cell.
