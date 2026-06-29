#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
    printf 'run as root on the target board\n' >&2
    exit 1
fi

IFACE=${1:-eth0}
PARENT=${PARENT:-100:1}
: "${IDLESLOPE:?set IDLESLOPE before running setup_cbs.sh}"
: "${SENDSLOPE:?set SENDSLOPE before running setup_cbs.sh}"
: "${HICREDIT:?set HICREDIT before running setup_cbs.sh}"
: "${LOCREDIT:?set LOCREDIT before running setup_cbs.sh}"
OFFLOAD=${OFFLOAD:-1}

printf '==> Apply CBS on %s parent %s\n' "$IFACE" "$PARENT"
tc qdisc replace dev "$IFACE" parent "$PARENT" cbs \
    idleslope "$IDLESLOPE" \
    sendslope "$SENDSLOPE" \
    hicredit "$HICREDIT" \
    locredit "$LOCREDIT" \
    offload "$OFFLOAD"

printf '==> Active qdisc on %s\n' "$IFACE"
tc qdisc show dev "$IFACE"
tc -s qdisc show dev "$IFACE"
