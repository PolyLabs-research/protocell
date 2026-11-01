# The plan: a single cell that manages light

**Agreed:** 2026-11-01, by the owner ("agree on all"), after the quantum-rat project's part 2 had three times failed to
test what it was built to (quantum-rat `docs/decisions.md` G58, G60, G62). There a whole of thirteen parts, each tuned
on its own, produced results through interactions no one had looked at in advance: the body's motor noise found the
food, a smell field covered two thirds of the floor, a measure could not register memory's benefit. This project starts
from first principles instead: the simplest organism, few parts, each understood, and complexity added only when a test
needs it. The hypothesis is the same: behaviour emerges from the interaction of parts.

## The organism

A single cell whose wall and brain are one neural structure.

```
          o — o — o
        /     |     \          o   wall node: senses light, beats a cilium
       o    ┌───┐    o         —   ring links: each node to its two neighbours (a closed loop)
       |  — │ C │ —  |         C   core: a small recurrent network
       o    └───┘    o         every wall node ↔ core, both ways
        \     |     /
          o — o — o
```

- **One network.** Wall nodes and core neurons are neurons of one continuous-time recurrent network (a CTRNN; Beer
  1995), with one weight matrix and a mask that allows only the ring's links, the spokes to and from the core, and the
  core's own links.
- **The wall senses and moves.** Each wall node receives the light at its place on the membrane and drives a cilium.
  The core steers by feeding back into the wall: sensing, integrating and moving are one loop.
- **Repeated membrane units.** Every wall node has the same wiring, tiled around the ring.
- **Low Reynolds number.** At a cell's scale there is no momentum: velocity is proportional to the summed push of the
  cilia, rotation to their summed torque.
- **Light is food, and too much light harms.** Energy comes from light absorbed, saturating as photosynthesis does;
  resting and beating cost energy; light above a threshold damages, and damage is repaired slowly. Death comes at zero
  energy or full damage. The cell must manage its exposure, not only maximise it.

## How it is optimised

**Evolution first.** Single cells are wired by evolution, not taught. A population of cells, each scored on its lifetime
energy over several light layouts, evolves the network's weights. Learning within a lifetime comes later, possibly by
evolving the learning rule. Gradient-based training only as a performance ceiling, if at all.

## Lessons carried over from quantum-rat

1. **Baselines before any optimisation:** a cell that does not move, a randomly wired cell, and a hand-wired reflex
   cell (each node's light drives its own cilium). The network matters only where it beats the reflex.
2. **The world's geometry and economy are checked before anything runs:** the light's difference across one cell
   body against the sensor noise, the distance to the light against the lifetime, whether moving pays at all.
3. **Every source of randomness is listed and can be switched off on its own.**
4. **For an agent in balance, effort per unit of light is measured beside the light gained.**
5. **The same discipline:** a preregistration before every build and run, design probes on fresh seeds, a decisions
   log, bit-for-bit determinism, runs from a clean tree with numerical warnings as errors.

## Stages (each ends with the owner's go or stop)

| stage | question | what decides it |
|---|---|---|
| 0 | The repository, CI, determinism, the physics, the light fields, energy, the baselines | Moving pays; the light can be sensed and reached; the reflex cell's score is known (`docs/prereg/stage0.md`) |
| 1 | Light seeking: does an evolved cell beat the reflex cell, including on layouts it never saw? | Removals: cut the ring links, open the loop, remove the core, remove the core's recurrence |
| 2 | Light management: with damage, does it hold position at the safe edge? | Time at the optimum against the baselines |
| 3 | Shallow gradients, too faint to sense across the body: does comparing over time evolve? | Removing the core's recurrence should break it |
| 4 | Changing light (day and night, moving spots); learning within a lifetime | The owner's call when we get there |

## Compute

Python 3.11 and numpy, as quantum-rat. Each cell is small (16 wall nodes and 8 core neurons to start), so a whole
population is simulated at once in numpy arrays, and populations or seeds spread over the machine's cores with a process
pool. No GPU is needed. RunPod only if runs grow, with the cost confirmed by the owner before every launch.
