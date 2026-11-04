#!/usr/bin/env bash
# Configure and record one endpoint of the P3 Qbu fragmentation measurement.
set -euo pipefail

RUN=${RUN:?}
ROLE=${ROLE:?}
MODE=${MODE:?}
ACTION=${ACTION:?}
DEV=${DEV:?}
SIBLING_DEV=${SIBLING_DEV:?}
LOCAL_IP=${LOCAL_IP:?}
PEER_IP=${PEER_IP:?}
PREEMPTIBLE_RATE=${PREEMPTIBLE_RATE:-80M}
EXPRESS_RATE=${EXPRESS_RATE:-10M}
PREEMPTIBLE_LENGTH=${PREEMPTIBLE_LENGTH:-1472}
EXPRESS_LENGTH=${EXPRESS_LENGTH:-1472}
DURATION_SEC=${DURATION_SEC:-30}
PREEMPTIBLE_CPU=${PREEMPTIBLE_CPU:-}
EXPRESS_CPU=${EXPRESS_CPU:-}
PACING_TIMER_US=${PACING_TIMER_US:-}
RECEIVER_RMEM_DEFAULT=${RECEIVER_RMEM_DEFAULT:-}
TX_MIN_FRAG_SIZE=${TX_MIN_FRAG_SIZE:-124}
TELEMETRY_INTERVAL_SEC=${TELEMETRY_INTERVAL_SEC:-}

mkdir -p "$RUN"

capture() {
    local suffix=$1
    ethtool "$DEV" > "$RUN/link-${suffix}.txt" 2>&1 || true
    ethtool -i "$DEV" > "$RUN/driver-${suffix}.txt" 2>&1 || true
    ethtool -l "$DEV" > "$RUN/channels-${suffix}.txt" 2>&1 || true
    ethtool --show-priv-flags "$DEV" > "$RUN/priv-flags-${suffix}.txt" 2>&1 || true
    ethtool --include-statistics --show-mm "$DEV" > "$RUN/mm-${suffix}.txt" 2>&1 || true
    ethtool -S "$DEV" > "$RUN/counters-${suffix}.txt" 2>&1 || true
    tc -s qdisc show dev "$DEV" > "$RUN/qos-${suffix}.txt" 2>&1 || true
    tc -s filter show dev "$DEV" egress > "$RUN/filters-${suffix}.txt" 2>&1 || true
    ip -s link show dev "$DEV" > "$RUN/link-stats-${suffix}.txt" 2>&1 || true
    cat /proc/loadavg > "$RUN/loadavg-${suffix}.txt"
    cat /sys/devices/system/cpu/online > "$RUN/cpu-online-${suffix}.txt"
    grep -E '8000000\.ethernet-(tx2|tx3|rx0)' /proc/interrupts > "$RUN/cpsw-irq-${suffix}.txt" 2>&1 || true
    grep -E 'NET_RX|NET_TX' /proc/softirqs > "$RUN/softirq-${suffix}.txt" 2>&1 || true
    cat /proc/net/snmp > "$RUN/net-snmp-${suffix}.txt"
    cat /proc/net/netstat > "$RUN/net-netstat-${suffix}.txt"
    cat /proc/net/softnet_stat > "$RUN/softnet-stat-${suffix}.txt"
    uname -a > "$RUN/uname-${suffix}.txt"
    cat /proc/sys/kernel/random/boot_id > "$RUN/boot-id-${suffix}.txt"
    cat "/sys/class/net/$DEV/address" > "$RUN/local-mac.txt"
    {
        printf 'preemptible_cpu=%s\n' "${PREEMPTIBLE_CPU:-scheduler-default}"
        printf 'express_cpu=%s\n' "${EXPRESS_CPU:-scheduler-default}"
        printf 'pacing_timer_us=%s\n' "${PACING_TIMER_US:-iperf3-default-1000}"
        printf 'receiver_rmem_default=%s\n' "${RECEIVER_RMEM_DEFAULT:-kernel-default}"
        printf 'tx_min_frag_size=%s\n' "$TX_MIN_FRAG_SIZE"
    } > "$RUN/generator-config.txt"
}

setup() {
    if [ "$ROLE" = receiver ]; then
        tc qdisc del dev "$DEV" root 2>/dev/null || true
    fi
    ip addr flush dev "$DEV"
    ip link set "$SIBLING_DEV" down
    ip link set "$DEV" down
    ethtool -L "$DEV" tx 4
    ethtool --set-priv-flags "$DEV" p0-rx-ptype-rrobin off
    if [ "$MODE" = on ]; then
        ethtool --set-mm "$DEV" pmac-enabled on tx-enabled on verify-enabled on verify-time 10 tx-min-frag-size "$TX_MIN_FRAG_SIZE"
    else
        ethtool --set-mm "$DEV" pmac-enabled off tx-enabled off verify-enabled off
    fi
    ip link set "$DEV" up
    # Match the proven Qbu procedure: allow PHY/MM verification to settle before IP/QoS setup.
    sleep 5
    ip addr replace "$LOCAL_IP/24" dev "$DEV"

    if [ "$ROLE" = receiver ] && [ -n "$RECEIVER_RMEM_DEFAULT" ]; then
        sysctl -n net.core.rmem_default > "$RUN/rmem-default-original.txt"
        sysctl -w "net.core.rmem_default=$RECEIVER_RMEM_DEFAULT" > "$RUN/rmem-default-applied.txt"
    fi

    if [ "$ROLE" = sender ]; then
        tc qdisc del dev "$DEV" root 2>/dev/null || true
        tc qdisc del dev "$DEV" clsact 2>/dev/null || true
        tc qdisc replace dev "$DEV" root handle 100: mqprio \
            num_tc 4 map 0 1 2 3 3 3 3 3 3 3 3 3 3 3 3 3 \
            queues 1@0 1@1 1@2 1@3 hw 1 mode dcb fp P P P E
        tc qdisc replace dev "$DEV" clsact
        tc filter replace dev "$DEV" egress protocol ip prio 1 u32 \
            match ip dport 5002 0xffff action skbedit priority 2
        tc filter replace dev "$DEV" egress protocol ip prio 2 u32 \
            match ip dport 5003 0xffff action skbedit priority 3
    fi
}

restore_receiver_rmem_default() {
    [ "$ROLE" = receiver ] || return
    local original="$RUN/rmem-default-original.txt"
    [ -f "$original" ] || original="$(dirname "$RUN")/on/rmem-default-original.txt"
    [ -f "$original" ] || return
    sysctl -w "net.core.rmem_default=$(cat "$original")" >/dev/null || true
}

wait_for_udp_listener() {
    local port=$1 hex
    hex=$(printf '%04X' "$port")
    for _ in {1..50}; do
        grep -q ":${hex} " /proc/net/udp && return
        sleep 0.1
    done
    printf 'iperf3 UDP server did not listen on port %s\n' "$port" >&2
    return 1
}

sample_endpoint_telemetry() {
    local stats udp in_errors rcvbuf processed dropped squeeze tx2_irq tx3_irq rx_irq
    local start_epoch now_epoch sample_index=0
    start_epoch=$(date +%s)
    printf 'epoch_s,sample_index,elapsed_s,udp_in_errors,udp_rcvbuf_errors,softnet_processed,softnet_dropped,softnet_time_squeeze,cpsw_tx2_irq,cpsw_tx3_irq,cpsw_rx0_irq,iet_tx_frag,iet_rx_frag,iet_rx_assembly_ok,iet_rx_assembly_err,iet_rx_smd_err\n' > "$RUN/endpoint-telemetry.csv"
    touch "$RUN/endpoint-telemetry.ready"
    while :; do
        udp=$(awk '$1 == "Udp:" { n++; if (n == 2) print $4 "," $6 }' /proc/net/snmp)
        read -r processed dropped squeeze _ < /proc/net/softnet_stat
        stats=$(ethtool -S "$DEV")
        # Sum every online CPU column. TX3 is serviced on TMDS CPU1, so
        # selecting only the first count column would falsely report zero.
        tx2_irq=$(awk '/8000000\.ethernet-tx2/ { s=0; for (i=2; i<=NF && $i ~ /^[0-9]+$/; i++) s+=$i; print s; exit }' /proc/interrupts)
        tx3_irq=$(awk '/8000000\.ethernet-tx3/ { s=0; for (i=2; i<=NF && $i ~ /^[0-9]+$/; i++) s+=$i; print s; exit }' /proc/interrupts)
        rx_irq=$(awk '/8000000\.ethernet-rx0/ { s=0; for (i=2; i<=NF && $i ~ /^[0-9]+$/; i++) s+=$i; print s; exit }' /proc/interrupts)
        in_errors=${udp%,*}
        rcvbuf=${udp#*,}
        now_epoch=$(date +%s)
        sample_index=$((sample_index + 1))
        printf '%s,%s,%s,%s,%s,0x%s,0x%s,0x%s,%s,%s,%s,%s,%s,%s,%s,%s\n' \
            "$now_epoch" "$sample_index" "$((now_epoch - start_epoch))" "$in_errors" "$rcvbuf" "$processed" "$dropped" "$squeeze" \
            "$tx2_irq" "$tx3_irq" "$rx_irq" \
            "$(awk '$1 == "iet_tx_frag:" { print $2 }' <<< "$stats")" \
            "$(awk '$1 == "iet_rx_frag:" { print $2 }' <<< "$stats")" \
            "$(awk '$1 == "iet_rx_assembly_ok:" { print $2 }' <<< "$stats")" \
            "$(awk '$1 == "iet_rx_assembly_err:" { print $2 }' <<< "$stats")" \
            "$(awk '$1 == "iet_rx_smd_err:" { print $2 }' <<< "$stats")" \
            >> "$RUN/endpoint-telemetry.csv"
        sleep "$TELEMETRY_INTERVAL_SEC"
    done
}

start_receiver_telemetry() {
    [ -n "$TELEMETRY_INTERVAL_SEC" ] || return
    rm -f "$RUN/endpoint-telemetry.pid" "$RUN/endpoint-telemetry.ready" \
        "$RUN/endpoint-telemetry.csv" "$RUN/endpoint-telemetry.log"
    setsid env RUN="$RUN" ROLE="$ROLE" MODE="$MODE" ACTION=monitor DEV="$DEV" \
        SIBLING_DEV="$SIBLING_DEV" LOCAL_IP="$LOCAL_IP" PEER_IP="$PEER_IP" \
        DURATION_SEC="$DURATION_SEC" PREEMPTIBLE_RATE="$PREEMPTIBLE_RATE" \
        EXPRESS_RATE="$EXPRESS_RATE" PREEMPTIBLE_LENGTH="$PREEMPTIBLE_LENGTH" \
        EXPRESS_LENGTH="$EXPRESS_LENGTH" PREEMPTIBLE_CPU="$PREEMPTIBLE_CPU" \
        EXPRESS_CPU="$EXPRESS_CPU" PACING_TIMER_US="$PACING_TIMER_US" \
        RECEIVER_RMEM_DEFAULT="$RECEIVER_RMEM_DEFAULT" TX_MIN_FRAG_SIZE="$TX_MIN_FRAG_SIZE" \
        TELEMETRY_INTERVAL_SEC="$TELEMETRY_INTERVAL_SEC" "$0" \
        > "$RUN/endpoint-telemetry.log" 2>&1 < /dev/null &
    printf '%s\n' "$!" > "$RUN/endpoint-telemetry.pid"
    for _ in {1..50}; do
        [ -s "$RUN/endpoint-telemetry.csv" ] && [ -f "$RUN/endpoint-telemetry.ready" ] && return
        sleep 0.1
    done
    printf 'receiver telemetry did not become ready\n' >&2
    return 1
}

stop_receiver_telemetry() {
    local pid_file="$RUN/endpoint-telemetry.pid"
    [ -f "$pid_file" ] || return
    kill -TERM "$(cat "$pid_file")" 2>/dev/null || true
    rm -f "$pid_file" "$RUN/endpoint-telemetry.ready"
}

cleanup() {
    for pid_file in "$RUN"/*.pid; do
        [ -e "$pid_file" ] || continue
        kill -TERM "$(cat "$pid_file")" 2>/dev/null || true
    done
    tc qdisc del dev "$DEV" root 2>/dev/null || true
    tc qdisc del dev "$DEV" clsact 2>/dev/null || true
    ethtool --set-mm "$DEV" pmac-enabled off tx-enabled off verify-enabled off 2>/dev/null || true
    restore_receiver_rmem_default
    ip link set "$SIBLING_DEV" up
    sleep 5
}

reset() {
    ip addr flush dev "$DEV"
    restore_receiver_rmem_default
}

case "$ACTION" in
    setup)
        setup
        ;;
    snapshot-before)
        sleep 5
        capture before
        ;;
    peer-proof)
        arping -c 3 -I "$DEV" "$PEER_IP" > "$RUN/peer-proof.txt" 2>&1
        ;;
    serve)
        [ "$ROLE" = receiver ]
        iperf3 -s -1 -B "$LOCAL_IP" -p 5002 --json > "$RUN/traffic-5002-server.json" 2>&1 &
        printf '%s\n' "$!" > "$RUN/server-5002.pid"
        taskset -pc "$!" > "$RUN/server-5002-affinity.txt" 2>&1 || true
        iperf3 -s -1 -B "$LOCAL_IP" -p 5003 --json > "$RUN/traffic-5003-server.json" 2>&1 &
        printf '%s\n' "$!" > "$RUN/server-5003.pid"
        taskset -pc "$!" > "$RUN/server-5003-affinity.txt" 2>&1 || true
        wait_for_udp_listener 5002
        wait_for_udp_listener 5003
        ;;
    send)
        [ "$ROLE" = sender ]
        preemptible_cmd=(iperf3 -c "$PEER_IP" -u -b "$PREEMPTIBLE_RATE" -l "$PREEMPTIBLE_LENGTH" -t "$DURATION_SEC" -p 5002 --json)
        express_cmd=(iperf3 -c "$PEER_IP" -u -b "$EXPRESS_RATE" -l "$EXPRESS_LENGTH" -t "$DURATION_SEC" -p 5003 --json)
        if [ -n "$PACING_TIMER_US" ]; then
            preemptible_cmd+=(--pacing-timer "$PACING_TIMER_US")
            express_cmd+=(--pacing-timer "$PACING_TIMER_US")
        fi
        if [ -n "$PREEMPTIBLE_CPU" ]; then
            preemptible_cmd=(taskset -c "$PREEMPTIBLE_CPU" "${preemptible_cmd[@]}")
        fi
        if [ -n "$EXPRESS_CPU" ]; then
            express_cmd=(taskset -c "$EXPRESS_CPU" "${express_cmd[@]}")
        fi
        "${preemptible_cmd[@]}" \
            > "$RUN/traffic-5002-client.json" 2>&1 &
        printf '%s\n' "$!" > "$RUN/client-5002.pid"
        taskset -pc "$!" > "$RUN/client-5002-affinity.txt" 2>&1 || true
        "${express_cmd[@]}" \
            > "$RUN/traffic-5003-client.json" 2>&1 &
        printf '%s\n' "$!" > "$RUN/client-5003.pid"
        taskset -pc "$!" > "$RUN/client-5003-affinity.txt" 2>&1 || true
        wait "$(cat "$RUN/client-5002.pid")"
        wait "$(cat "$RUN/client-5003.pid")"
        ;;
    monitor)
        sample_endpoint_telemetry
        ;;
    start-telemetry)
        start_receiver_telemetry
        ;;
    stop-telemetry)
        stop_receiver_telemetry
        ;;
    snapshot-after)
        capture after
        ;;
    cleanup)
        cleanup
        ;;
    reset)
        reset
        ;;
    *)
        printf 'unknown ACTION: %s\n' "$ACTION" >&2
        exit 2
        ;;
esac
