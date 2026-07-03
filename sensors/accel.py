"""MPU6050 accelerometer/gyroscope helpers for future expansion."""

import adafruit_mpu6050


def init_sensors(mux, channels):
    return {
        name: adafruit_mpu6050.MPU6050(mux[channel])
        for name, channel in channels.items()
    }


def read_sensors(sensors):
    readings = {}

    for name, sensor in sensors.items():
        try:
            ax, ay, az = sensor.acceleration
            gx, gy, gz = sensor.gyro
            readings[name] = {
                "accel_ms2": [ax, ay, az],
                "gyro_rads": [gx, gy, gz],
            }
        except Exception as exc:  # noqa: BLE001 - keep the loop alive on bad reads.
            readings[name] = {"error": str(exc)}

    return readings
