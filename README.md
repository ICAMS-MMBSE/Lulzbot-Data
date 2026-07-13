# Lulzbot Multi-Sensor MQTT Monitoring

External sensor telemetry for a Lulzbot 3D printer, published over MQTT to a
local Mosquitto broker on the OctoPrint Raspberry Pi. Eight I2C sensors sit
behind a SparkFun Qwiic Mux (PCA9548A, `0x70`); a validation module compares
externally measured toolhead position against OctoPrint's reported position.

The service is fully independent of OctoPrint: it never touches the printer
serial port or the camera, and the printer keeps printing if this service dies.

## Architecture

```
config.yaml ──> load_config ──> driver registry ──> [Sensor drivers]
                                                        │ each driver holds a
                                                        │ TCA9548A[channel] as
                                                        │ its I2C bus
[SensorWorker thread per sensor] ──(shared bus lock)──> mux ──> hardware
        │ readings
        ├──> MQTT telemetry  Lulzbot/<suffix>          (per-sensor JSON)
        ├──> PositionFuser ──> Lulzbot/position        (fused X/Y/Z)
        └──> health state  ──> Lulzbot/status/<name>   (retained)

OctoPrint MQTT plugin ──> octoPrint/event/ZChange, PositionUpdate
        └──> OctoPrintComparator ──> Lulzbot/validation/<axis> + CSV
```

Key properties:

* **Mux correctness.** Drivers are constructed with `mux[channel]` as their
  I2C bus, so channel selection is structural -- there is no manual
  select-then-read sequence to get wrong. A single re-entrant lock serializes
  all transactions across channels; each worker holds it only for one read.
* **Scheduling.** One paced thread per sensor (monotonic clock), so a 0.5 Hz
  BME280 never blocks a 100 Hz accelerometer. Rates come from config.
* **Graceful degradation.** A sensor that fails to init or read is logged,
  reported on its status topic, and retried with exponential backoff
  (1 s -> 60 s cap). Other sensors are unaffected; the service never exits
  because one device died.
* **Uniform payloads.** Every message carries `ts` (ISO 8601 UTC), `seq`
  (per-topic monotonic), `sensor_id`, `role`, `values`, `units`, `quality`.

## Mux channel map (default -- change in config, never in code)

| Ch | Sensor   | Addr | Role                              | Default rate |
|----|----------|------|-----------------------------------|--------------|
| 0  | VL53L0X  | 0x29 | Z position (toolhead-mounted)     | 20 Hz |
| 1  | VL53L1X  | 0x29 | X position (frame-mounted)        | 20 Hz |
| 2  | VL53L1X  | 0x29 | Y position (frame-mounted)        | 20 Hz |
| 3  | ADXL345  | 0x53 | Buildplate vibration              | 100 Hz |
| 4  | MPU6050  | 0x68 | Printhead motion                  | 100 Hz |
| 5  | AMG8833  | 0x69 | 8x8 thermal view                  | 5 Hz |
| 6  | BME280   | 0x77 | Ambient environment               | 0.5 Hz |
| 7  | VCNL4010 | 0x13 | Person presence                   | 5 Hz |

The three ToF sensors all default to `0x29`; giving each its own channel
sidesteps the address conflict with no XSHUT/address-reprogram dance.

## MQTT topic reference

| Topic                             | Content                          | Retained |
|-----------------------------------|----------------------------------|----------|
| `Lulzbot/position`                | Fused X/Y/Z (mm) + source sensors| no |
| `Lulzbot/position/x` `/y` `/z`    | Per-sensor distance + position   | no |
| `Lulzbot/acceleration/buildplate` | ADXL345 3-axis accel             | no |
| `Lulzbot/acceleration/printhead`  | MPU6050 accel + gyro + temp      | no |
| `Lulzbot/thermal`                 | AMG8833 8x8 grid + min/max/mean  | no |
| `Lulzbot/environment`             | BME280 temp/humidity/pressure    | no |
| `Lulzbot/proximity`               | VCNL4010 counts + `person_present` | no |
| `Lulzbot/status/<sensor_name>`    | Per-sensor health                | yes |
| `Lulzbot/status/system`           | Service online/offline (LWT)     | yes |
| `Lulzbot/validation/<axis>`       | OctoPrint-vs-ToF residuals       | no |

Example telemetry payload:

```json
{"ts": "2026-07-09T16:21:04.512Z", "seq": 8412, "sensor_id": "tof_z",
 "role": "z_position", "values": {"distance_mm": 142.3, "position_mm": 142.3},
 "units": {"distance_mm": "mm", "position_mm": "mm"}, "quality": "ok"}
```

## Install (Raspberry Pi)

```bash
# 0. Local broker (if not already present)
sudo apt install mosquitto mosquitto-clients
# 1. Service
sudo bash scripts/install.sh
# 2. Edit /etc/lulzbot-sensors/config.yaml (offsets, thresholds)
# 3. Verify wiring (see WIRING.md)
/opt/lulzbot-sensors/venv/bin/python -m sensor_service \
    --config /etc/lulzbot-sensors/config.yaml --probe
# 4. Run
sudo systemctl start lulzbot-sensors
journalctl -u lulzbot-sensors -f
```

To mirror telemetry into the factory monitoring system later, add a Mosquitto
bridge on the Pi (`/etc/mosquitto/conf.d/factory-bridge.conf`):

```
connection factory
address factory-broker.example.edu:1883
topic Lulzbot/# out 0
```

## Development without hardware

Mock drivers implement the same `Sensor` ABC and produce realistic synthetic
streams. One config flag switches the whole pipeline:

```bash
python -m venv venv && venv/bin/pip install -r requirements-dev.txt
venv/bin/python -m sensor_service --config config/config.mock.yaml   # needs any reachable broker
venv/bin/python -m sensor_service --config config/config.mock.yaml --probe
venv/bin/pytest
```

## Sensor-swap procedure (worked example: MPU6050 -> BNO055)

Zero changes to the acquisition loop, scheduler, or MQTT layer:

1. **Write the driver** -- `sensor_service/drivers/bno055.py`:

   ```python
   from sensor_service.drivers.base import Sensor, SensorInitError, SensorReadError
   from sensor_service.drivers.registry import register

   @register("bno055")
   class BNO055Driver(Sensor):
       default_units = {"ax_ms2": "m/s^2", "ay_ms2": "m/s^2", "az_ms2": "m/s^2",
                        "heading_deg": "deg", "roll_deg": "deg", "pitch_deg": "deg"}

       def initialize(self):
           try:
               import adafruit_bno055   # lazy import, like every driver
               self._dev = adafruit_bno055.BNO055_I2C(self.i2c, address=self.config.address)
           except Exception as exc:
               raise SensorInitError(f"BNO055 init failed: {exc}") from exc

       def read(self):
           try:
               ax, ay, az = self._dev.acceleration
               h, r, p = self._dev.euler
           except Exception as exc:
               raise SensorReadError(f"BNO055 read failed: {exc}") from exc
           return {"ax_ms2": ax, "ay_ms2": ay, "az_ms2": az,
                   "heading_deg": h, "roll_deg": r, "pitch_deg": p}
   ```

2. **Register the import** -- add `bno055` to the imports in
   `sensor_service/drivers/__init__.py` (and a mock in `drivers/mock/` if you
   want dev-machine support).
3. **Pin the library** -- add `adafruit-circuitpython-bno055==x.y.z` to
   `requirements.txt`.
4. **Edit config** -- replace the MPU6050 block:

   ```yaml
   - name: imu_printhead
     driver: bno055          # was: mpu6050
     mux_channel: 4
     address: 0x28           # BNO055 default
     sample_rate_hz: 50
     topic_suffix: acceleration/printhead
     role: printhead_motion
   ```

5. `--probe` to confirm the device answers on channel 4, then restart.

## OctoPrint MQTT plugin setup

1. OctoPrint > Settings > Plugin Manager > *Get More...* > install from URL:
   `https://github.com/OctoPrint/OctoPrint-MQTT/archive/master.zip`
2. Settings > MQTT: broker host `localhost`, port `1883` (same local
   Mosquitto this service uses); leave the base topic at `octoPrint/`.
3. Restart OctoPrint. Verify with
   `mosquitto_sub -t 'octoPrint/#' -v` -- you should see `octoPrint/mqtt
   connected`, then events/temperatures.

What the plugin publishes (used by the validation module):

* `octoPrint/event/<Event>` -- all OctoPrint events as JSON with `_event` and
  unix `_timestamp`. Position-relevant: **`ZChange`** (`{"new": z, "old": z}`,
  fires on layer change) and **`PositionUpdate`** (`{"x":..,"y":..,"z":..}`,
  fires after an `M114` is answered).
* `octoPrint/progress/printing` (retained), `octoPrint/temperature/<tool|bed>`
  (retained), LWT on `octoPrint/mqtt`.

### Validation behaviour

Z is compared on every `ZChange` (primary, always available); X/Y are compared
whenever a `PositionUpdate` appears -- inject `M114` into gcode or poll it via
the OctoPrint terminal/API to enable that. The plugin's `_timestamp` is whole
seconds, so the comparator time-aligns on message *arrival* time instead
(fine on a localhost broker, ~ms). Residuals (`measured - commanded`) go to
`Lulzbot/validation/<axis>` and to CSV under `validation.csv_dir`.

If MQTT-side position proves too sparse in practice, the fallback is polling
the OctoPrint REST API (`/api/printer?exclude=temperature,sd` reports Z; a
plugin such as GcodeSystemCommands can schedule M114) -- but prefer the MQTT
path first.

## Repo layout

```
sensor_service/
  __main__.py        entrypoint: run | --probe | --validate-config
  core/              config, mux (+ lock), scheduler, MQTT client, payload, logging
  drivers/           Sensor ABC, registry, one driver per device, mock/ mirrors
  fusion/            ToF -> fused Lulzbot/position
  validation/        OctoPrint comparison: alignment (pure), comparator, CSV
config/              commented example + no-hardware mock config
tests/               config, registry, payload, topics, alignment, mock contract
systemd/, scripts/   service unit + installer
```
