#!/bin/sh
set -eu

systemctl daemon-reload
networkctl reload 2>/dev/null || true
systemctl restart systemd-networkd
sleep 2

printf '===== systemd-networkd =====\n'
systemctl is-active systemd-networkd || true

printf '\n===== ip -br link =====\n'
ip -br link

printf '\n===== ip -br addr =====\n'
ip -br addr

printf '\n===== bridge link =====\n'
bridge link || true

printf '\n===== bridge fdb =====\n'
bridge fdb show br br-tsn || true
