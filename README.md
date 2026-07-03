# Lulzbot-Data

Getting information from the Lulzbot: temperature, x-y-z values, acceleration and so on. Uploading that data into a database.

## Layout

- `main.py` is the primary entrypoint.
- `config.py` holds addresses, channel maps, and timing constants.
- `hardware.py` creates the I2C bus, mux, and ADS1115.
- `sensors/` contains sensor-specific setup and read logic.
- `payload.py` builds one JSON-ready reading.
- `outputs/` contains places a payload can go, such as console output or MQTT.

Run the current console acquisition loop from this folder:

```sh
python3 main.py
```

## Adding Or Updating Sensors

Most sensor changes should follow the same path:

1. Update `requirements.txt` if the sensor needs a new Python library.
2. Add or update channel/address settings in `config.py`.
3. Put sensor-specific setup and read code in `sensors/`.
4. Initialize the sensor group in `main.py`.
5. Add the sensor group to the JSON payload in `payload.py`.

Keep each sensor file shaped like the existing ones:

- `init_sensors(...)` creates the hardware objects.
- `read_sensors(...)` returns a plain Python dict.
- Sensor read errors should be captured per sensor so one bad sensor does not stop the whole acquisition loop.

For example, to enable the scaffolded AMG8833 thermal sensors:

1. Uncomment or add the thermal channel map in `config.py`:

```python
AMG_CHANNELS = {"thermal_0": 3, "thermal_1": 4}
```

2. Import and initialize them in `main.py`:

```python
from config import AMG_CHANNELS
from sensors.thermal import init_sensors as init_thermal_sensors


def init_sensor_stack():
    hardware = init_hardware()
    return {
        "tof": init_tof_sensors(hardware.mux, VL53_CHANNELS, TIMING_BUDGET_US),
        "ultrasonic": init_ultrasonic_sensors(hardware.ads, ULTRASONIC_CHANNELS),
        "thermal": init_thermal_sensors(hardware.mux, AMG_CHANNELS),
    }
```

3. Read them in `payload.py`:

```python
from sensors.thermal import read_sensors as read_thermal_sensors


def build_payload(tof_sensors=None, ultrasonic_sensors=None, thermal_sensors=None):
    payload = {"timestamp": utc_timestamp()}

    if thermal_sensors is not None:
        payload["thermal"] = read_thermal_sensors(thermal_sensors)

    return payload
```

If you add a totally new sensor type, create a new file like `sensors/new_sensor.py` and keep the same `init_sensors` / `read_sensors` pattern.
