#!/usr/bin/env bash
# Install the Lulzbot sensor service on a Raspberry Pi (Raspberry Pi OS).
# Run from the repo root:  sudo bash scripts/install.sh
set -euo pipefail

INSTALL_DIR=/opt/lulzbot-sensors
CONFIG_DIR=/etc/lulzbot-sensors
LOG_DIR=/var/log/lulzbot-sensors
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "==> Installing OS packages (python3-venv, i2c-tools, git)"
apt-get update -qq
apt-get install -y -qq python3-venv python3-dev i2c-tools

echo "==> Enabling I2C"
raspi-config nonint do_i2c 0 || echo "   (raspi-config not found -- enable I2C manually)"

echo "==> Copying code to ${INSTALL_DIR}"
mkdir -p "${INSTALL_DIR}"
rsync -a --delete --exclude venv --exclude .git "${REPO_DIR}/" "${INSTALL_DIR}/"

echo "==> Creating venv + installing pinned dependencies"
python3 -m venv "${INSTALL_DIR}/venv"
"${INSTALL_DIR}/venv/bin/pip" install --upgrade pip -q
"${INSTALL_DIR}/venv/bin/pip" install -r "${INSTALL_DIR}/requirements.txt" -q

echo "==> Config"
mkdir -p "${CONFIG_DIR}" "${LOG_DIR}"
chown pi:pi "${LOG_DIR}"
if [ ! -f "${CONFIG_DIR}/config.yaml" ]; then
    cp "${INSTALL_DIR}/config/config.example.yaml" "${CONFIG_DIR}/config.yaml"
    echo "   Created ${CONFIG_DIR}/config.yaml -- EDIT IT (broker, offsets) before starting."
fi

echo "==> Validating config"
"${INSTALL_DIR}/venv/bin/python" -m sensor_service \
    --config "${CONFIG_DIR}/config.yaml" --validate-config

echo "==> Installing systemd unit"
cp "${INSTALL_DIR}/systemd/lulzbot-sensors.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable lulzbot-sensors.service

cat <<MSG

Done. Next steps:
  1. Edit ${CONFIG_DIR}/config.yaml (broker host, ToF offsets, thresholds)
  2. Wire sensors, then verify:   ${INSTALL_DIR}/venv/bin/python -m sensor_service --config ${CONFIG_DIR}/config.yaml --probe
  3. Start:                       sudo systemctl start lulzbot-sensors
  4. Watch logs:                  journalctl -u lulzbot-sensors -f
MSG
