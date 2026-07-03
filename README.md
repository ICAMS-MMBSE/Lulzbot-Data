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
