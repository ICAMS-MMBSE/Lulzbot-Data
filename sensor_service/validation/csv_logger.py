"""CSV logging of validation residuals for offline analysis."""
from __future__ import annotations

import csv
import logging
import threading
import time
from pathlib import Path
from typing import Optional

from sensor_service.validation.alignment import AlignedPair

log = logging.getLogger("validation.csv")

HEADER = ["ts_unix", "source", "axis", "commanded_mm", "measured_mm",
          "residual_mm", "alignment_gap_s"]


class ResidualCsvLogger:
    def __init__(self, csv_dir: Optional[str]):
        self._lock = threading.Lock()
        self._writer = None
        self._file = None
        if csv_dir is None:
            log.info("csv_dir not set; residual CSV logging disabled")
            return
        directory = Path(csv_dir)
        directory.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d_%H%M%S")
        path = directory / f"residuals_{stamp}.csv"
        self._file = path.open("w", newline="", encoding="utf-8")
        self._writer = csv.writer(self._file)
        self._writer.writerow(HEADER)
        self._file.flush()
        log.info("Logging residuals to %s", path)

    def log(self, source: str, axis: str, pair: AlignedPair) -> None:
        if self._writer is None:
            return
        with self._lock:
            self._writer.writerow([
                f"{pair.ref_t:.3f}", source, axis,
                f"{pair.ref_value:.3f}", f"{pair.measured_value:.3f}",
                f"{pair.residual:.3f}", f"{pair.gap_s:.3f}",
            ])
            self._file.flush()

    def close(self) -> None:
        with self._lock:
            if self._file is not None:
                self._file.close()
                self._file = None
                self._writer = None
