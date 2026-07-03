"""Runtime configuration for the Lulzbot data acquisition scripts."""

MUX_ADDRESS = 0x70  # SparkFun Qwiic Mux (TCA9548A) default

# One VL53L0X per mux channel keeps their shared 0x29 address from colliding.
VL53_CHANNELS = {
    "tof_0": 0,
    "tof_1": 1,
    "tof_2": 2,
}

# MB1010 analog ultrasonic sensors connected to ADS1115 channels A0-A2.
ULTRASONIC_CHANNELS = {
    "ultrasonic_0": 0,
    "ultrasonic_1": 1,
    "ultrasonic_2": 2,
}

# Optional future hardware:
# AMG_CHANNELS = {"thermal_0": 3, "thermal_1": 4}
# ACCEL_CHANNELS = {"accel_0": 5, "accel_1": 6}

READ_PERIOD_S = 0.2
TIMING_BUDGET_US = 50000  # VL53L0X: raise for accuracy, lower for speed.

ADS_GAIN = 1  # +/-4.096V range; comfortably covers a 3.3V-referenced signal.
ULTRASONIC_REFERENCE_V = 3.3  # Used for the MB1010 distance estimate.
