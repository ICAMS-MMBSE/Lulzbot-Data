"""Time alignment for comparing OctoPrint position events to ToF telemetry.

Pure data structures + functions (no MQTT, no I/O) so this logic is fully
unit-testable. Strategy: keep a ring buffer of recent sensor samples per
axis; when an OctoPrint reference value arrives, find the sensor sample
nearest in time. If the gap exceeds ``max_gap_s`` the pair is rejected.
"""
from __future__ import annotations

import bisect
import threading
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass(frozen=True)
class Sample:
    t: float      # unix seconds
    value: float


@dataclass(frozen=True)
class AlignedPair:
    ref_t: float
    ref_value: float          # OctoPrint commanded/reported
    measured_t: float
    measured_value: float     # externally measured (ToF)
    gap_s: float

    @property
    def residual(self) -> float:
        """measured - commanded. Positive => sensor reads high."""
        return self.measured_value - self.ref_value


class SampleBuffer:
    """Thread-safe, time-ordered ring buffer of Samples."""

    def __init__(self, horizon_s: float = 15.0):
        self.horizon_s = horizon_s
        self._times: List[float] = []
        self._samples: List[Sample] = []
        self._lock = threading.Lock()

    def __len__(self) -> int:
        with self._lock:
            return len(self._samples)

    def append(self, sample: Sample) -> None:
        with self._lock:
            if self._times and sample.t < self._times[-1]:
                # Out-of-order arrival: insert in time order.
                i = bisect.bisect_left(self._times, sample.t)
                self._times.insert(i, sample.t)
                self._samples.insert(i, sample)
            else:
                self._times.append(sample.t)
                self._samples.append(sample)
            cutoff = sample.t - self.horizon_s
            while self._times and self._times[0] < cutoff:
                self._times.pop(0)
                self._samples.pop(0)

    def nearest(self, t: float) -> Optional[Tuple[Sample, float]]:
        """Sample nearest in time to ``t`` and the absolute gap, or None."""
        with self._lock:
            if not self._samples:
                return None
            i = bisect.bisect_left(self._times, t)
            candidates = []
            if i > 0:
                candidates.append(self._samples[i - 1])
            if i < len(self._samples):
                candidates.append(self._samples[i])
            best = min(candidates, key=lambda s: abs(s.t - t))
            return best, abs(best.t - t)


def align(buffer: SampleBuffer, ref_t: float, ref_value: float,
          max_gap_s: float) -> Optional[AlignedPair]:
    """Pair an OctoPrint reference with the nearest sensor sample, or None
    if nothing lands within ``max_gap_s``."""
    hit = buffer.nearest(ref_t)
    if hit is None:
        return None
    sample, gap = hit
    if gap > max_gap_s:
        return None
    return AlignedPair(ref_t=ref_t, ref_value=ref_value,
                       measured_t=sample.t, measured_value=sample.value, gap_s=gap)
