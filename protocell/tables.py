"""Writing the tables a run leaves beside its manifest: CSV with floats to 12 significant digits and booleans as 0/1."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np


def fmt(value: Any) -> Any:
    if isinstance(value, (bool, np.bool_)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        return format(float(value), ".12g")
    if isinstance(value, np.integer):
        return int(value)
    return value


def write_csv(path: Path, columns: Sequence[str], rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(columns), lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: fmt(row.get(k)) for k in columns})
