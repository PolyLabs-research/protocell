"""The network's structure as an interactive page, generated from the code so that it shows the network as it stands:
the topology mask, both spoke modes' genome layouts and ranges, which number of the genome sets which weight (found by
perturbing each number and decoding, not by restating the layout), and example genomes (the cave's random genomes 1–3
at its seed, the ones its B3 ran).

    .venv/bin/python -m tools.network_doc                                   # writes docs/network.html
    .venv/bin/python -m tools.network_doc --fragment --out /tmp/net.html    # without the document skeleton, for publishing
"""

from __future__ import annotations

import argparse
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import protocell  # noqa: F401  # pins the BLAS thread counts before numpy loads

import numpy as np

from experiments.cave import SEED
from protocell.cell import MODES, RING_NAMES, STREAM_GENOMES, decode, genome_ranges, layout, random_genomes, topology_mask
from protocell.config import CAVE, Config
from protocell.manifest import git_state
from protocell.rng import stream
from tools import pages

DEFAULT_OUT = Path("docs/network.html")
DELTA = 0.5  # the perturbation that finds what a number sets
N_EXAMPLES = 3
RING_LABELS = {
    "ring_self": "self weight, every wall neuron",
    "ring_from_cw": "weight from the clockwise neighbour",
    "ring_from_ccw": "weight from the anticlockwise neighbour",
    "ring_bias": "bias, every wall neuron",
    "ring_log_tau": "log τ, every wall neuron",
    "gain": "sensory gain g",
}
BLOCKS = {
    "core_w": ("Core weights", "core", "to core neuron j from core neuron l, each its own number"),
    "core_bias": ("Core biases", "core", "one per core neuron"),
    "core_log_tau": ("Core time constants", "core", "log τ, one per core neuron"),
    "ring": ("The ring's unit", "ring", "shared by all 16 wall neurons: the repeated membrane unit"),
    "alpha": ("Cilium angle", "ring", "α, shared by all 16 cilia"),
    "spokes_in": ("Spokes in", "spoke", "wall → core"),
    "spokes_out": ("Spokes out", "spoke", "core → wall"),
}
TERMS = ("a, constant", "b, × cos θ", "c, × sin θ")


def gene_name(block: str, r: int, mode: str, n_core: int) -> str:
    """A number's name from its block and its place in the block (r, 0-based)."""
    if block == "core_w":
        return f"core {r // n_core} ← core {r % n_core}"
    if block == "core_bias":
        return f"bias of core {r}"
    if block == "core_log_tau":
        return f"log τ of core {r}"
    if block == "ring":
        return RING_LABELS[RING_NAMES[r]]
    if block == "alpha":
        return "cilium angle α"
    arrow = "wall → core {j}" if block == "spokes_in" else "core {j} → wall"
    if mode == "uniform":
        return f"spoke {arrow.format(j=r)}"
    return f"spoke {arrow.format(j=r // 3)}, {TERMS[r % 3]}"


def _round(a: Any, digits: int = 4) -> Any:
    return np.round(np.asarray(a, dtype=np.float64), digits).tolist()


def describe_mode(cfg: Config, mode: str, seed: int) -> Dict[str, Any]:
    lay = layout(cfg, mode)
    lo, hi = genome_ranges(cfg, mode)
    examples = random_genomes(cfg, mode, N_EXAMPLES, stream(seed, STREAM_GENOMES))
    base = examples[0]
    p0 = decode(cfg, mode, base[None])
    blocks: List[Dict[str, Any]] = []
    genes: List[Dict[str, Any]] = []
    for key, sl in (("core_w", lay.core_w), ("core_bias", lay.core_bias), ("core_log_tau", lay.core_log_tau), ("ring", lay.ring),
                    ("alpha", lay.alpha), ("spokes_in", lay.spokes_in), ("spokes_out", lay.spokes_out)):
        label, family, note = BLOCKS[key]
        blocks.append({"key": key, "label": label, "family": family, "note": note, "start": sl.start, "stop": sl.stop})
        for g in range(sl.start, sl.stop):
            moved = base.copy()
            moved[g] += DELTA
            p1 = decode(cfg, mode, moved[None])
            dW = (p1.W[0] - p0.W[0]) / DELTA
            entries = [[int(i), int(j), round(float(dW[i, j]), 4)] for i, j in np.argwhere(np.abs(dW) > 1e-9)]
            genes.append({"index": g, "block": key, "name": gene_name(key, g - sl.start, mode, cfg.n_core),
                          "lo": round(float(lo[g]), 4), "hi": round(float(hi[g]), 4), "W": entries,
                          "bias": np.flatnonzero(np.abs(p1.bias[0] - p0.bias[0]) > 1e-12).tolist(),
                          "tau": np.flatnonzero(np.abs(p1.tau[0] - p0.tau[0]) > 1e-12).tolist(),
                          "gain": bool(p1.gain[0] != p0.gain[0]), "alpha": bool(p1.alpha[0] != p0.alpha[0])})
    decoded = decode(cfg, mode, examples)
    ex = [{"label": f"random genome {n + 1}", "genome": _round(examples[n]), "W": _round(decoded.W[n]), "bias": _round(decoded.bias[n]),
           "tau": _round(decoded.tau[n], 3), "gain": round(float(decoded.gain[n]), 4), "alpha": round(float(decoded.alpha[n]), 4)}
          for n in range(N_EXAMPLES)]
    return {"length": lay.length, "blocks": blocks, "genes": genes, "examples": ex}


def describe(cfg: Config = CAVE, seed: int = SEED) -> Dict[str, Any]:
    """Everything the page shows, read from the code."""
    git = git_state()
    return {
        "n_wall": cfg.n_wall, "n_core": cfg.n_core,
        "mask": topology_mask(cfg).astype(int).tolist(),
        "modes": {mode: describe_mode(cfg, mode, seed) for mode in MODES},
        "params": {"weight_range": list(cfg.weight_range), "tau_range": [math.exp(cfg.log_tau_range[0]), math.exp(cfg.log_tau_range[1])],
                   "gain_range": list(cfg.gain_range), "v_max": cfg.v_max, "omega_max": cfg.omega_max,
                   "sensor_noise_sd": cfg.sensor_noise_sd, "rotation_noise_sd": cfg.rotation_noise_sd},
        "provenance": {"sha": git["sha"], "dirty": git["dirty"], "seed": seed,
                       "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds")},
    }


def main(argv: Optional[Sequence[str]] = None) -> Path:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--fragment", action="store_true", help="write the page without its document skeleton (for publishing)")
    args = parser.parse_args(argv)
    out = pages.write(args.out, "network.html", describe(), fragment=args.fragment)
    print(f"written to {out} ({out.stat().st_size / 1e3:.0f} kB)")
    return out


if __name__ == "__main__":
    main(sys.argv[1:])
