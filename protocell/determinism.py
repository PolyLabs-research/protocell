"""The numerical rules that make a run reproducible bit for bit on the same platform (docs/determinism.md).

Imports nothing heavy at module level: ``protocell/__init__.py`` imports this before numpy can load.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict

BLAS_THREAD_VARS = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")
_NUMPY_LOADED_BEFORE_PIN = "numpy" in sys.modules


def pin_blas_threads() -> None:
    """One BLAS/OpenMP thread, unless the environment already says otherwise: threaded reductions can change the order
    of a floating-point sum, and so its last bits. Parallelism comes from processes, not threads."""
    for name in BLAS_THREAD_VARS:
        os.environ.setdefault(name, "1")


def blas_info() -> Dict[str, Any]:
    """The numerical facts a manifest records: numpy's version, the BLAS the loaded library reports and its threads."""
    info: Dict[str, Any] = {"numpy": None, "blas_runtime": None, "blas_threads": {v: os.environ.get(v) for v in BLAS_THREAD_VARS},
                            "numpy_loaded_before_pin": _NUMPY_LOADED_BEFORE_PIN}
    try:
        import numpy

        info["numpy"] = numpy.__version__
    except ImportError:  # pragma: no cover - numpy is a dependency
        return info
    try:
        from threadpoolctl import threadpool_info

        info["blas_runtime"] = [{k: lib.get(k) for k in ("internal_api", "version", "architecture", "num_threads")}
                                for lib in threadpool_info() if lib.get("user_api") == "blas"]
    except ImportError:  # pragma: no cover
        pass
    return info
