#!/usr/bin/env bash
set -euo pipefail

CFG=${1:-/tmp/gptp-endpoint-qbv.cfg}

cat > "$CFG" <<'EOF'
[global]
network_transport L2
delay_mechanism P2P
time_stamping hardware
twoStepFlag 1
summary_interval 1
logging_level 6
tx_timestamp_timeout 100
EOF

printf '%s\n' "$CFG"
