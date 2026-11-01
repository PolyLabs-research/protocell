"""protocell: a single cell whose wall and brain are one neural network (docs/plan.md).

Importing ``protocell`` pins the BLAS/OpenMP thread counts to 1 (``protocell.determinism.pin_blas_threads``,
docs/determinism.md). The runtimes read the variables when numpy's extension loads, so the pin takes effect only when
``protocell`` is imported before the first ``import numpy``; a value already set in the environment is left alone.
"""

from protocell.determinism import pin_blas_threads as _pin_blas_threads

_pin_blas_threads()
