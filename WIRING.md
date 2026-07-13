# Wiring & Verification Checklist

## Wiring

1. Qwiic mux (PCA9548A) to the Pi: SDA -> GPIO2 (pin 3), SCL -> GPIO3 (pin 5),
   3.3 V, GND. Leave the mux at its default address `0x70` (no ADR jumpers).
2. One sensor per mux channel, per the channel map (README). The three ToF
   boards MUST be on separate channels -- they share address `0x29`.
3. Keep the 100 Hz accelerometer leads short; I2C at 100 kHz over long Qwiic
   runs is the first thing to flake.

## Verification (before starting the service)

**Step 1 -- main bus.** Only the mux should be visible upstream:

```bash
i2cdetect -y 1
```

Expected: `0x70` only. If a sensor address also appears here, it is wired to
the main bus instead of a mux channel (or a Qwiic cable bypasses the mux).
Note: some AMG8833/BME280 boards would collide with nothing here anyway --
but behind the mux is where they belong.

**Step 2 -- per channel.** `i2cdetect` can't select mux channels by itself;
use the built-in probe, which scans all 8 channels through the mux and diffs
against config:

```bash
/opt/lulzbot-sensors/venv/bin/python -m sensor_service \
    --config /etc/lulzbot-sensors/config.yaml --probe
```

Expected output (PASS):

```
ch  found                expected                     result
 0  0x29                 tof_z @ 0x29                 OK
 1  0x29                 tof_x @ 0x29                 OK
 2  0x29                 tof_y @ 0x29                 OK
 3  0x53                 accel_buildplate @ 0x53      OK
 4  0x68                 imu_printhead @ 0x68         OK
 5  0x69                 thermal_cam @ 0x69           OK
 6  0x77                 environment @ 0x77           OK
 7  0x13                 proximity @ 0x13             OK
PROBE PASS
```

Manual per-channel check (equivalent, if you prefer raw i2cdetect): write the
channel bitmask to the mux, then scan --

```bash
i2cset -y 1 0x70 0x08   # 0x08 = 1<<3 = select channel 3
i2cdetect -y 1          # expect 0x53 (and 0x70 itself)
i2cset -y 1 0x70 0x00   # deselect all channels when done
```

| Channel | bitmask | expect |
|---------|---------|--------|
| 0 | 0x01 | 0x29 |
| 1 | 0x02 | 0x29 |
| 2 | 0x04 | 0x29 |
| 3 | 0x08 | 0x53 |
| 4 | 0x10 | 0x68 |
| 5 | 0x20 | 0x69 |
| 6 | 0x40 | 0x77 |
| 7 | 0x80 | 0x13 |

**Step 3 -- MPU6050 address check.** `0x68` conflicts with nothing in this
build, but if AD0 is pulled high the device answers at `0x69` (colliding with
the AMG8833 *if they shared a channel* -- they don't). If probe shows `0x69`
on channel 4, tie AD0 low or set `address: 0x69` in config.

**Step 4 -- AMG8833 address check.** Default `0x69`; with the address jumper
set it becomes `0x68`. Match config to reality; probe will tell you.

**Step 5 -- broker + service dry run.**

```bash
mosquitto_sub -t 'Lulzbot/#' -v &
sudo systemctl start lulzbot-sensors
```

Expect retained `Lulzbot/status/system {"online": true, ...}` immediately,
per-sensor `Lulzbot/status/<name>` with `"status": "ok"`, then telemetry.

## ToF calibration (offsets live in config, not code)

* `tof_z` (toolhead-mounted, ranging down): home Z, read
  `Lulzbot/position/z` -> `distance_mm`, set `offset_mm: -<that value>` so
  position reads 0 at home. `sign: 1.0`.
* `tof_x` / `tof_y` (frame-mounted, ranging at the toolhead): home the axis,
  read `distance_mm`, set `sign: -1.0`, `offset_mm: +<that value>`.
* Sanity-check at a second known position (e.g. jog to 100 mm) before
  trusting validation residuals.
