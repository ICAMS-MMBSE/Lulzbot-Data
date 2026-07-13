"""Synthetic implementations of every driver, one per real sensor type."""
from __future__ import annotations

import math
import random
import time
from typing import Any, Dict

from sensor_service.drivers.base import Sensor, apply_axis_transform
from sensor_service.drivers.registry import register


class _MockBase(Sensor):
    """Common plumbing: deterministic-ish per-sensor RNG and a time origin."""

    def initialize(self) -> None:
        self._t0 = time.monotonic()
        self._rng = random.Random(hash(self.name) & 0xFFFFFFFF)

    def _t(self) -> float:
        return time.monotonic() - self._t0

    def _noise(self, scale: float) -> float:
        return self._rng.gauss(0.0, scale)


@register("vl53l0x", mock=True)
class MockVL53L0X(_MockBase):
    default_units = {"distance_mm": "mm", "position_mm": "mm"}

    def read(self) -> Dict[str, Any]:
        # Z creeps upward like layers accumulating, 0-120 mm sawtooth.
        d = 20.0 + (self._t() * 0.05 % 120.0) + self._noise(0.8)
        return {"distance_mm": d, "position_mm": apply_axis_transform(d, self.config.params)}


@register("vl53l1x", mock=True)
class MockVL53L1X(_MockBase):
    default_units = {"distance_mm": "mm", "position_mm": "mm"}

    def read(self) -> Dict[str, Any]:
        # Travel moves: triangle wave across ~250 mm plus noise.
        period = 30.0
        phase = (self._t() % period) / period
        tri = 2 * abs(phase - 0.5)  # 1 -> 0 -> 1
        d = 30.0 + 250.0 * tri + self._noise(1.2)
        return {"distance_mm": d, "position_mm": apply_axis_transform(d, self.config.params)}


@register("adxl345", mock=True)
class MockADXL345(_MockBase):
    default_units = {"ax_ms2": "m/s^2", "ay_ms2": "m/s^2", "az_ms2": "m/s^2"}

    def read(self) -> Dict[str, Any]:
        t = self._t()
        return {
            "ax_ms2": 0.4 * math.sin(2 * math.pi * 7.0 * t) + self._noise(0.05),
            "ay_ms2": 0.3 * math.sin(2 * math.pi * 11.0 * t) + self._noise(0.05),
            "az_ms2": 9.81 + 0.2 * math.sin(2 * math.pi * 3.0 * t) + self._noise(0.05),
        }


@register("mpu6050", mock=True)
class MockMPU6050(_MockBase):
    default_units = {
        "ax_ms2": "m/s^2", "ay_ms2": "m/s^2", "az_ms2": "m/s^2",
        "gx_rads": "rad/s", "gy_rads": "rad/s", "gz_rads": "rad/s",
        "temp_c": "degC",
    }

    def read(self) -> Dict[str, Any]:
        t = self._t()
        return {
            "ax_ms2": 1.2 * math.sin(2 * math.pi * 5.0 * t) + self._noise(0.08),
            "ay_ms2": 1.0 * math.cos(2 * math.pi * 5.0 * t) + self._noise(0.08),
            "az_ms2": 9.81 + self._noise(0.08),
            "gx_rads": 0.02 * math.sin(2 * math.pi * 1.0 * t) + self._noise(0.005),
            "gy_rads": 0.02 * math.cos(2 * math.pi * 1.0 * t) + self._noise(0.005),
            "gz_rads": self._noise(0.005),
            "temp_c": 32.0 + self._noise(0.1),
        }


@register("amg8833", mock=True)
class MockAMG8833(_MockBase):
    default_units = {"grid_c": "degC[8x8]", "min_c": "degC", "max_c": "degC", "mean_c": "degC"}

    def read(self) -> Dict[str, Any]:
        # Warm gaussian blob (nozzle/bed) drifting over a cool background.
        t = self._t()
        cx = 3.5 + 2.0 * math.sin(t / 12.0)
        cy = 3.5 + 2.0 * math.cos(t / 17.0)
        grid = []
        for y in range(8):
            row = []
            for x in range(8):
                d2 = (x - cx) ** 2 + (y - cy) ** 2
                row.append(round(24.0 + 45.0 * math.exp(-d2 / 3.0) + self._noise(0.4), 2))
            grid.append(row)
        flat = [px for row in grid for px in row]
        return {"grid_c": grid, "min_c": min(flat), "max_c": max(flat),
                "mean_c": sum(flat) / len(flat)}


@register("bme280", mock=True)
class MockBME280(_MockBase):
    default_units = {"temp_c": "degC", "humidity_pct": "%RH", "pressure_hpa": "hPa"}

    def read(self) -> Dict[str, Any]:
        t = self._t()
        return {
            "temp_c": 23.5 + 1.5 * math.sin(t / 600.0) + self._noise(0.05),
            "humidity_pct": 45.0 + 5.0 * math.sin(t / 900.0) + self._noise(0.2),
            "pressure_hpa": 1002.0 + self._noise(0.1),
        }


@register("vcnl4010", mock=True)
class MockVCNL4010(_MockBase):
    default_units = {"proximity_counts": "counts", "ambient_lux": "lux", "person_present": "bool"}

    def initialize(self) -> None:
        super().initialize()
        self._present = False

    def read(self) -> Dict[str, Any]:
        # Someone walks up for ~20 s out of every 90 s.
        near = (self._t() % 90.0) < 20.0
        prox = (5200.0 if near else 2050.0) + self._noise(60.0)
        thr = float(self.config.params.get("present_threshold", 2200))
        hyst = float(self.config.params.get("hysteresis", 200))
        if self._present:
            self._present = prox > (thr - hyst)
        else:
            self._present = prox > (thr + hyst)
        return {"proximity_counts": prox, "ambient_lux": 320.0 + self._noise(5.0),
                "person_present": self._present}
