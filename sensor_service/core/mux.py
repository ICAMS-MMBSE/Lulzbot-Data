"""TCA9548A / PCA9548A mux access.

Channel selection is structural: each driver is handed ``mux[channel]``
(an ``adafruit_tca9548a`` channel object) as its I2C bus, so every
transaction automatically selects the right channel -- there is no manual
"switch then read" sequence to get wrong.

All bus access across channels is serialized with a single re-entrant
lock (``bus_lock``); acquisition threads must hold it for the duration of
one read to prevent channel races.
"""
from __future__ import annotations

import threading
from typing import Any, Dict, List

from sensor_service.core.config import MuxConfig

NUM_CHANNELS = 8


class MuxError(Exception):
    pass


class I2CMux:
    """Real TCA9548A behind Blinka. Imports hardware libs lazily."""

    def __init__(self, cfg: MuxConfig):
        self.cfg = cfg
        self.bus_lock = threading.RLock()
        try:
            import board  # noqa: PLC0415 - requires Blinka; Pi only
            import adafruit_tca9548a  # noqa: PLC0415
        except (ImportError, NotImplementedError) as exc:
            raise MuxError(
                "Hardware I2C unavailable (is this a Pi with Blinka installed "
                "and I2C enabled?). Use use_mock_drivers: true for dev machines."
            ) from exc
        i2c = board.I2C()
        self._mux = adafruit_tca9548a.TCA9548A(i2c, address=cfg.address)

    def channel(self, n: int) -> Any:
        if not 0 <= n < NUM_CHANNELS:
            raise MuxError(f"Mux channel {n} out of range 0-{NUM_CHANNELS - 1}")
        return self._mux[n]

    def scan_channel(self, n: int) -> List[int]:
        """Addresses visible on channel ``n`` (mux's own address excluded)."""
        ch = self.channel(n)
        with self.bus_lock:
            while not ch.try_lock():
                pass
            try:
                found = ch.scan()
            finally:
                ch.unlock()
        return sorted(a for a in found if a != self.cfg.address)

    def scan_all(self) -> Dict[int, List[int]]:
        return {n: self.scan_channel(n) for n in range(NUM_CHANNELS)}


class MockMux:
    """No-hardware stand-in. Channel objects are inert placeholders and the
    scan map is synthesized from config so ``--probe`` works in mock mode."""

    def __init__(self, cfg: MuxConfig, scan_map: Dict[int, List[int]] | None = None):
        self.cfg = cfg
        self.bus_lock = threading.RLock()
        self._scan_map = scan_map or {}

    def channel(self, n: int) -> Any:
        if not 0 <= n < NUM_CHANNELS:
            raise MuxError(f"Mux channel {n} out of range 0-{NUM_CHANNELS - 1}")
        return f"mock-i2c-channel-{n}"

    def scan_channel(self, n: int) -> List[int]:
        return sorted(self._scan_map.get(n, []))

    def scan_all(self) -> Dict[int, List[int]]:
        return {n: self.scan_channel(n) for n in range(NUM_CHANNELS)}
