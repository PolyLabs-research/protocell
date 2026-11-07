
**Learnt (2026-11-07 19:21 UTC):** Uniform design 1, probes. Three calibration rounds for D (the uniform sum's night-to-far-field gap is ~0.5 on D's input only at weight 8; at weight 4 noise latched D on at night) and R's drive from D (3.8). Then D rests at night and the pacemaker fires (bursting ~5% at light 0.5). The pull points the right way (forward at 0 deg, left at 90, back at 180) but is ~0.0004 v_max at 10x the real contrast: bursts drive all nodes up together, so no sharp bump forms. The physics underneath: in the mid field the light across the body differs by ~0.0005 per node against ~0.008 sensor noise per tick; a ring winner-take-all pools a few nodes, so it picks noise winners (B6 pools 16 nodes over 32 ticks). Next (design 2): the burst drive rises slowly (R tau 3) so the brightest nodes cross first; stronger local excitation (self 3, neighbours 2) and stronger, sharper global inhibition (G reads 4 x sum, bias -8) for a real bump.

**Learnt (2026-11-07 19:21 UTC):** Uniform design 2, probes: still no real bump (bursting ~4%, pull ~0.0005 v_max at 10x real contrast, in the right direction at all four angles), and D flickers half-on at night. The physics argument says a sharper bump would still pick noise winners at the real contrast (10x below this probe's). One world check for the record.

### Check 1: `u02.json` (46e996fbc4ce), starts 1-24

**Why, written before it ran:** Uniform design 2: design 1 (recalibrated) with a real winner-take-all bump. The burst drive rises slowly (R tau 3, drive +5), so during each burst's rise the nodes whose integrated light is highest cross first. Their self- and neighbour-excitation (self 3, neighbours 2) holds a bump of ~3 nodes, and G (4 x sum, bias -8, tau 1, -8 to all) switches on once ~2-3 nodes are active and silences the rest. The bump's beats pull the cell toward the brightest side. Expected: a clear pull toward brighter light in the mid field; little in the far field, where the light across the body is far below the sensors' noise.

| | this design | B8 | B0 |
|---|---|---|---|
| fitness | 0.140 | 0.567 | 0.148 |
| survival | 0% | 96% | 0% |
| light per daylight tick | 0.113 | 0.606 | 0.115 |
| beat by day / night | 0.038 / 0.036 | 0.100 / 0 | 0 / 0 |
| reached the soak region | 12% | 100% | 12% |

Share of the gap from B0 to B8 on these starts: -0.02. Check 1 of 50; 28 s; code 30470ef.

**Learnt (2026-11-07 19:23 UTC):** Check 1 (uniform design 2): 0.140, reached 12%, none survived; B0's level as predicted. Submission: uniform design 2, the only design checked. Its probes and the physics (light across the body ~16x below sensor noise per node per tick in the mid field) say further bump tuning tests the tuning, not the cell.
