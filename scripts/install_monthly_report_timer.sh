#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UNIT_DIR="$(cd "$SCRIPT_DIR/../systemd" && pwd)"

if [[ "$EUID" -eq 0 ]]; then
  install -m 0644 "$UNIT_DIR/portfolio-monthly-report.service" /etc/systemd/system/portfolio-monthly-report.service
  install -m 0644 "$UNIT_DIR/portfolio-monthly-report.timer" /etc/systemd/system/portfolio-monthly-report.timer
  systemctl daemon-reload
  systemctl enable --now portfolio-monthly-report.timer
  systemctl list-timers portfolio-monthly-report.timer --no-pager
else
  systemctl --user link "$UNIT_DIR/portfolio-monthly-report.service" "$UNIT_DIR/portfolio-monthly-report.timer"
  systemctl --user daemon-reload
  systemctl --user enable --now portfolio-monthly-report.timer
  systemctl --user list-timers portfolio-monthly-report.timer --no-pager
fi
