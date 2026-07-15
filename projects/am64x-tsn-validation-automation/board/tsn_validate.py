#!/usr/bin/env python3
"""UART-only AM64x TSN validation runner.

The runner intentionally keeps all board configuration in temporary runtime
state. It does not deploy rootfs overlays or assume SSH connectivity.
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = PROJECT_DIR.parents[1]
UARTCTL = ROOT_DIR / "tools" / "uart" / "uartctl.py"
LOG_ROOT = PROJECT_DIR / "logs"
PROMPT = "# "
DATA_PORTS = {"sk": ("eth0", "eth1"), "tmds": ("eth1", "eth2")}
EXPECTED_PAIRS = {"eth0": "eth1", "eth1": "eth2"}


class ValidationError(RuntimeError):
    pass


class Runner:
    def __init__(self, run_dir: Path, timeout: int, runtime_sec: int):
        self.run_dir = run_dir
        self.timeout = timeout
        self.runtime_sec = runtime_sec
        self.run_dir.mkdir(parents=True, exist_ok=True)

    def command(self, target: str, label: str, command: str, timeout: int | None = None) -> str:
        request = [
            str(UARTCTL), "--target", target, "command", command,
            "--expect", PROMPT, "--timeout", str(timeout or self.timeout), "--fresh",
        ]
        completed = subprocess.run(request, text=True, capture_output=True, check=False)
        record = {
            "target": target,
            "label": label,
            "command": command,
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
        (self.run_dir / f"command-{target}-{label}.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        if completed.returncode:
            raise ValidationError(f"{target}:{label} UART command failed: {completed.stderr.strip()}")
        try:
            response = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise ValidationError(f"{target}:{label} did not return UART JSON") from exc
        if not response.get("ok"):
            raise ValidationError(f"{target}:{label} UART request failed: {response}")
        return str(response.get("output", ""))

    def script(self, target: str, label: str, script: str, timeout: int | None = None) -> str:
        encoded = base64.b64encode(script.encode("utf-8")).decode("ascii")
        transfer_path = f"/tmp/tsn-auto-{label}.b64"
        chunk_size = 384
        for index, start in enumerate(range(0, len(encoded), chunk_size)):
            chunk = encoded[start:start + chunk_size]
            redirect = ">" if index == 0 else ">>"
            self.command(
                target,
                f"{label}-transfer-{index:02d}",
                f"printf %s {chunk} {redirect} {transfer_path}",
                timeout,
            )
        output = self.command(
            target,
            label,
            f"base64 -d {transfer_path} | /bin/sh; rc=$?; rm -f {transfer_path}; printf '__TSN_REMOTE_STATUS=%s\\n' \"$rc\"",
            timeout,
        )
        statuses = re.findall(r"^__TSN_REMOTE_STATUS=(\d+)\r?$", output, flags=re.MULTILINE)
        if not statuses:
            raise ValidationError(f"{target}:{label} did not return a remote exit status")
        if statuses[-1] != "0":
            raise ValidationError(f"{target}:{label} remote script exited with status {statuses[-1]}")
        return output

    def save(self, name: str, content: str) -> None:
        (self.run_dir / name).write_text(content, encoding="utf-8")


def port_state_script(interfaces: tuple[str, ...]) -> str:
    quoted = " ".join(interfaces)
    return f"""set -eu
for dev in {quoted}; do
    carrier=$(cat /sys/class/net/$dev/carrier 2>/dev/null || printf 0)
    state=$(cat /sys/class/net/$dev/operstate 2>/dev/null || printf unknown)
    mac=$(cat /sys/class/net/$dev/address)
    speed=$(ethtool $dev 2>/dev/null | awk '/Speed:/ {{print $2}}')
    driver=$(ethtool -i $dev 2>/dev/null | awk -F': ' '/^driver:/ {{print $2}}')
    printf 'TSN_IF dev=%s carrier=%s state=%s speed=%s mac=%s driver=%s\\n' \\
        "$dev" "$carrier" "$state" "${{speed:-unknown}}" "$mac" "${{driver:-unknown}}"
done
"""


def parse_port_states(output: str) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for line in output.splitlines():
        if not line.startswith("TSN_IF "):
            continue
        values = dict(item.split("=", 1) for item in line.split()[1:] if "=" in item)
        if "dev" in values:
            result[values["dev"]] = values
    return result


def require_link(states: dict[str, dict[str, str]], dev: str) -> None:
    item = states.get(dev)
    if not item:
        raise ValidationError(f"missing state for {dev}")
    if item.get("carrier") != "1" or item.get("speed") != "1000Mb/s":
        raise ValidationError(f"{dev} is not a 1 Gbps carrier: {item}")


def preflight(runner: Runner, bring_up_links: bool, prove_pairs: bool) -> dict[str, Any]:
    if bring_up_links:
        runner.script("sk", "bring-up-data-links", "ip link set eth0 up\nip link set eth1 up\n")
        runner.script("tmds", "bring-up-data-links", "ip link set eth1 up\nip link set eth2 up\n")
        time.sleep(4)

    sk_output = runner.script("sk", "preflight-ports", port_state_script(DATA_PORTS["sk"]))
    tmds_output = runner.script("tmds", "preflight-ports", port_state_script(DATA_PORTS["tmds"]))
    runner.save("preflight-sk.txt", sk_output)
    runner.save("preflight-tmds.txt", tmds_output)
    sk = parse_port_states(sk_output)
    tmds = parse_port_states(tmds_output)
    for dev in DATA_PORTS["sk"]:
        require_link(sk, dev)
    for dev in DATA_PORTS["tmds"]:
        require_link(tmds, dev)

    evidence: dict[str, Any] = {"sk": sk, "tmds": tmds, "pairs": {}}
    if not prove_pairs:
        return evidence

    # The probes are L2 broadcasts only. No interface address is added or changed.
    sk_eth0_mac = sk["eth0"]["mac"]
    sk_eth1_mac = sk["eth1"]["mac"]
    runner.script("tmds", "start-pair-capture", f"""set -eu
rm -f /tmp/tsn-auto-pair-eth1.txt /tmp/tsn-auto-pair-eth2.txt
timeout 12 tcpdump -i eth1 -n -e -c 1 'arp and ether src {sk_eth0_mac}' > /tmp/tsn-auto-pair-eth1.txt 2>&1 &
timeout 12 tcpdump -i eth2 -n -e -c 1 'arp and ether src {sk_eth1_mac}' > /tmp/tsn-auto-pair-eth2.txt 2>&1 &
sleep 1
""")
    runner.script("sk", "send-pair-probes", """set -eu
arping -I eth0 -c 1 -w 2 198.18.0.10 >/dev/null 2>&1 || true
arping -I eth1 -c 1 -w 2 198.18.0.11 >/dev/null 2>&1 || true
sleep 1
""")
    captures = runner.script("tmds", "read-pair-capture", """sleep 2
printf '%s\\n' '[eth1]'
cat /tmp/tsn-auto-pair-eth1.txt
printf '%s\\n' '[eth2]'
cat /tmp/tsn-auto-pair-eth2.txt
""")
    runner.save("preflight-pair-proof.txt", captures)
    for sk_dev, tmds_dev in EXPECTED_PAIRS.items():
        source = sk[sk_dev]["mac"].lower()
        marker = f"[{tmds_dev}]"
        section = captures.split(marker, 1)[1] if marker in captures else ""
        evidence["pairs"][f"sk-{sk_dev}__tmds-{tmds_dev}"] = source in section.lower()
        if source not in section.lower():
            raise ValidationError(
                f"pair proof failed: SK {sk_dev} ARP was not captured on TMDS {tmds_dev}"
            )
    return evidence


def baseline_state_script(target: str) -> str:
    interfaces = "eth0 eth1" if target == "sk" else "eth1 eth2"
    switch_mode_command = "devlink dev param show platform/8000000.ethernet 2>/dev/null | awk '/cmode runtime value/ {print $NF}'" if target == "sk" else "printf na"
    bridge_command = "test -e /sys/class/net/br-tsn && printf present || printf absent" if target == "sk" else "printf na"
    service_command = "printf na" if target == "sk" else "systemctl is-enabled ti-tsn-dscp-pcp-tmds.service 2>/dev/null || true"
    return f"""set -eu
switch_mode=$({switch_mode_command})
bridge=$({bridge_command})
service=$({service_command})
processes=0
for process in ptp4l phc2sys iperf3 tcpdump; do
    pgrep -x "$process" >/dev/null 2>&1 && processes=1
done
printf 'TSN_BASE board={target} switch_mode=%s bridge=%s netns=%s service=%s processes=%s\\n' \\
    "${{switch_mode:-unknown}}" "${{bridge:-unknown}}" "$(ip netns list | wc -l)" "${{service:-unknown}}" "$processes"
for dev in {interfaces}; do
    addr=$(ip -4 -o addr show dev "$dev" | wc -l)
    custom=0
    if tc qdisc show dev "$dev" | grep -Eq 'taprio|mqprio|cbs|clsact'; then custom=1; fi
    pmac=$(ethtool --show-mm "$dev" 2>/dev/null | awk -F ': ' '/pMAC enabled/ {{print $2}}')
    tx=$(ethtool --show-mm "$dev" 2>/dev/null | awk -F ': ' '/TX enabled/ {{print $2}}')
    verify=$(ethtool --show-mm "$dev" 2>/dev/null | awk -F ': ' '/Verify enabled/ {{print $2}}')
    queues=$(ethtool -l "$dev" 2>/dev/null | awk 'BEGIN {{current=0}} /^Current hardware settings:/ {{current=1}} current && /^TX:/ {{print $2; exit}}')
    printf 'TSN_BASE_IF dev=%s addr=%s custom_qdisc=%s pmac=%s tx=%s verify=%s queues=%s\\n' \\
        "$dev" "$addr" "$custom" "${{pmac:-unknown}}" "${{tx:-unknown}}" "${{verify:-unknown}}" "${{queues:-unknown}}"
done
"""


def parse_baseline_state(output: str) -> tuple[dict[str, str], dict[str, dict[str, str]]]:
    board: dict[str, str] = {}
    interfaces: dict[str, dict[str, str]] = {}
    for line in output.splitlines():
        if line.startswith("TSN_BASE "):
            board = dict(item.split("=", 1) for item in line.split()[1:] if "=" in item)
        elif line.startswith("TSN_BASE_IF "):
            values = dict(item.split("=", 1) for item in line.split()[1:] if "=" in item)
            if "dev" in values:
                interfaces[values["dev"]] = values
    return board, interfaces


def check_baseline(runner: Runner) -> dict[str, Any]:
    sk_output = runner.script("sk", "baseline-check", baseline_state_script("sk"))
    tmds_output = runner.script("tmds", "baseline-check", baseline_state_script("tmds"))
    runner.save("baseline-sk.txt", sk_output)
    runner.save("baseline-tmds.txt", tmds_output)
    sk_board, sk_ifaces = parse_baseline_state(sk_output)
    tmds_board, tmds_ifaces = parse_baseline_state(tmds_output)
    failures: list[str] = []

    if sk_board.get("switch_mode") != "false":
        failures.append(f"SK switch_mode={sk_board.get('switch_mode')}")
    if sk_board.get("bridge") != "absent":
        failures.append("SK br-tsn exists")
    if sk_board.get("netns") != "0":
        failures.append(f"SK network namespaces={sk_board.get('netns')}")
    if tmds_board.get("netns") != "0":
        failures.append(f"TMDS network namespaces={tmds_board.get('netns')}")
    if tmds_board.get("service") not in {"disabled", "not-found", "masked"}:
        failures.append(f"TMDS TSN auto service={tmds_board.get('service')}")
    if sk_board.get("processes") != "0":
        failures.append("SK TSN test process is running")
    if tmds_board.get("processes") != "0":
        failures.append("TMDS TSN test process is running")

    for board, interfaces in (("SK", sk_ifaces), ("TMDS", tmds_ifaces)):
        for dev, state in interfaces.items():
            if state.get("addr") != "0":
                failures.append(f"{board} {dev} has IPv4 address")
            if state.get("custom_qdisc") != "0":
                failures.append(f"{board} {dev} has TSN qdisc")
    for dev in ("eth0", "eth1"):
        state = sk_ifaces.get(dev, {})
        if state.get("pmac") != "off" or state.get("tx") != "off" or state.get("verify") != "off":
            failures.append(f"SK {dev} MAC Merge is not disabled")
    if sk_ifaces.get("eth0", {}).get("queues") != "8":
        failures.append(f"SK eth0 TX queues={sk_ifaces.get('eth0', {}).get('queues')}")
    tmds_eth1 = tmds_ifaces.get("eth1", {})
    if any(tmds_eth1.get(item) != "off" for item in ("pmac", "tx", "verify")):
        failures.append("TMDS eth1 MAC Merge is not disabled")
    if tmds_eth1.get("queues") != "8":
        failures.append(f"TMDS eth1 TX queues={tmds_eth1.get('queues')}")

    state = {"sk": {"board": sk_board, "interfaces": sk_ifaces}, "tmds": {"board": tmds_board, "interfaces": tmds_ifaces}}
    if failures:
        raise ValidationError("shared-clean-v1 baseline check failed: " + "; ".join(failures))
    return state


def apply_baseline(runner: Runner) -> None:
    runner.script("sk", "baseline-apply", """set -eu
pkill ptp4l 2>/dev/null || true
pkill phc2sys 2>/dev/null || true
pkill iperf3 2>/dev/null || true
ip link del br-tsn 2>/dev/null || true
for dev in eth0.301 eth0.311 eth1.301; do ip link del $dev 2>/dev/null || true; done
ip link set eth0 down
ip link set eth1 down
for dev in eth0 eth1; do tc qdisc del dev $dev root 2>/dev/null || true; tc qdisc del dev $dev clsact 2>/dev/null || true; ip addr flush dev $dev 2>/dev/null || true; ethtool --set-mm $dev pmac-enabled off tx-enabled off verify-enabled off 2>/dev/null || true; done
ethtool -L eth0 tx 8 2>/dev/null || true
ip link set eth0 up
ip link set eth1 up
devlink dev param set platform/8000000.ethernet name switch_mode value false cmode runtime 2>/dev/null || true
""")
    runner.script("tmds", "baseline-apply", """set -eu
pkill ptp4l 2>/dev/null || true
pkill phc2sys 2>/dev/null || true
pkill iperf3 2>/dev/null || true
pkill tcpdump 2>/dev/null || true
rm -f /tmp/tsn-auto-dscp.pcap /tmp/tsn-auto-dscp-capture.pid /tmp/tsn-auto-qbv.pcap /tmp/tsn-auto-qbv-capture.pid
ip netns del ep1 2>/dev/null || true
ip netns del ep2 2>/dev/null || true
for dev in eth1.301 eth2.301 eth1.311; do ip link del $dev 2>/dev/null || true; done
ip link set eth1 down
ip link set eth2 down
for dev in eth1 eth2; do tc qdisc del dev $dev root 2>/dev/null || true; tc qdisc del dev $dev clsact 2>/dev/null || true; ip addr flush dev $dev 2>/dev/null || true; done
ethtool --set-mm eth1 pmac-enabled off tx-enabled off verify-enabled off 2>/dev/null || true
ethtool -L eth1 tx 8 2>/dev/null || true
ip link set eth1 up
ip link set eth2 up
""")


def run_gptp(runner: Runner) -> dict[str, Any]:
    config = """[global]
network_transport L2
delay_mechanism P2P
time_stamping hardware
twoStepFlag 1
summary_interval 1
logging_level 6
"""
    encoded = base64.b64encode(config.encode()).decode()
    for target, dev in (("sk", "eth1"), ("tmds", "eth2")):
        runner.script(target, f"gptp-start-{dev}", f"""set -eu
printf %s {encoded} | base64 -d > /tmp/tsn-auto-gptp.cfg
pkill ptp4l 2>/dev/null || true
ptp4l -i {dev} -f /tmp/tsn-auto-gptp.cfg -m > /tmp/tsn-auto-gptp.log 2>&1 &
echo $! > /tmp/tsn-auto-gptp.pid
""")
    time.sleep(runner.runtime_sec)
    sk_log = runner.script("sk", "gptp-log", "cat /tmp/tsn-auto-gptp.log; kill $(cat /tmp/tsn-auto-gptp.pid) 2>/dev/null || true\n")
    tmds_log = runner.script("tmds", "gptp-log", "cat /tmp/tsn-auto-gptp.log; kill $(cat /tmp/tsn-auto-gptp.pid) 2>/dev/null || true\n")
    runner.save("sk-ptp.log", sk_log)
    runner.save("tmds-ptp.log", tmds_log)
    return {"tmds_slave": "to SLAVE" in tmds_log, "tmds_log": "tmds-ptp.log"}


def run_dscp_pcp(runner: Runner) -> dict[str, Any]:
    runner.script("sk", "dscp-pcp-switchdev", """set -eu
tc qdisc del dev eth0 root 2>/dev/null || true
tc qdisc del dev eth1 root 2>/dev/null || true
ip link del br-tsn 2>/dev/null || true
ip addr flush dev eth0
ip addr flush dev eth1
ethtool --set-priv-flags eth0 p0-rx-ptype-rrobin off
ethtool --set-priv-flags eth1 p0-rx-ptype-rrobin off
devlink dev param set platform/8000000.ethernet name switch_mode value true cmode runtime
ip link add br-tsn type bridge
ip link set eth0 up
ip link set eth1 up
ip link set eth0 master br-tsn
ip link set eth1 master br-tsn
ip link set br-tsn up
ip link set br-tsn type bridge vlan_filtering 1
bridge vlan add dev br-tsn vid 1 pvid untagged self
bridge vlan add dev eth0 vid 301 master
bridge vlan add dev eth1 vid 301 master
bridge vlan add dev br-tsn vid 301 self
tc qdisc replace dev eth0 root handle 100: mqprio num_tc 3 map 2 2 1 0 2 2 2 2 2 2 2 2 2 2 2 2 queues 1@0 1@1 2@2 hw 1 mode channel
tc qdisc replace dev eth1 root handle 100: mqprio num_tc 3 map 2 2 1 0 2 2 2 2 2 2 2 2 2 2 2 2 queues 1@0 1@1 2@2 hw 1 mode channel
sleep 5
""".replace("\n+", "\n"), 60)
    runner.script("tmds", "dscp-pcp-endpoints", """set -eu
ip netns del ep1 2>/dev/null || true
ip netns del ep2 2>/dev/null || true
ip netns add ep1
ip netns add ep2
ip link set eth1 netns ep1
ip link set eth2 netns ep2
ip -n ep1 link set lo up
ip -n ep2 link set lo up
ip -n ep1 link set eth1 up
ip -n ep2 link set eth2 up
ip -n ep1 link add link eth1 name eth1.301 type vlan id 301
ip -n ep2 link add link eth2 name eth2.301 type vlan id 301
ip -n ep1 addr add 10.31.0.2/24 dev eth1.301
ip -n ep2 addr add 10.31.0.1/24 dev eth2.301
ip -n ep1 link set eth1.301 up
ip -n ep2 link set eth2.301 type vlan egress 0:0 1:1 2:2 3:3 4:4 5:5 6:6 7:7
ip -n ep2 link set eth2.301 up
ip netns exec ep2 tc qdisc add dev eth2.301 clsact
ip netns exec ep2 tc filter add dev eth2.301 egress protocol ip prio 1 u32 match ip dport 5001 0xffff action skbedit priority 7
ip netns exec ep2 tc filter add dev eth2.301 egress protocol ip prio 2 u32 match ip dport 5002 0xffff action skbedit priority 6
ip netns exec ep1 iperf3 -s -D -p 5001
ip netns exec ep1 iperf3 -s -D -p 5002
ip netns exec ep1 tcpdump -i eth1 -w /tmp/tsn-auto-dscp.pcap 'vlan and udp' >/dev/null 2>&1 &
echo $! > /tmp/tsn-auto-dscp-capture.pid
sleep 5
ip netns exec ep2 ping -c 2 -W 2 -I eth2.301 10.31.0.2
""".replace("\n+", "\n"), 60)
    runner.script("tmds", "dscp-pcp-traffic", f"""set -eu
ip netns exec ep2 iperf3 -c 10.31.0.2 -u -b 20M -t {runner.runtime_sec} -p 5001
ip netns exec ep2 iperf3 -c 10.31.0.2 -u -b 20M -t {runner.runtime_sec} -p 5002
""", runner.runtime_sec * 3 + 30)
    capture = runner.script("tmds", "dscp-pcp-read-capture", """set -eu
kill -INT $(cat /tmp/tsn-auto-dscp-capture.pid) 2>/dev/null || true
sleep 1
printf '%s\\n' '[udp5001]'
ip netns exec ep1 tcpdump -r /tmp/tsn-auto-dscp.pcap -n -e -c 1 'vlan and udp port 5001' 2>&1 || true
printf '%s\\n' '[udp5002]'
ip netns exec ep1 tcpdump -r /tmp/tsn-auto-dscp.pcap -n -e -c 1 'vlan and udp port 5002' 2>&1 || true
""")
    runner.save("dscp-pcp-capture.txt", capture)
    return {"pcp7": "vlan 301, p 7" in capture, "pcp6": "vlan 301, p 6" in capture}


def run_qbv(runner: Runner) -> dict[str, Any]:
    runner.script("sk", "qbv-sender", """set -eu
ip link set eth1 down
ip link set eth0 down
ethtool -L eth0 tx 3
ethtool --set-priv-flags eth0 p0-rx-ptype-rrobin off
ip link set eth0 up
sleep 5
ip link add link eth0 name eth0.311 type vlan id 311
ip link set eth0.311 type vlan egress 0:0 1:1 2:2 3:3 4:4 5:5 6:6 7:7
ip link set eth0.311 up
sleep 2
ip addr flush dev eth0.311
ip addr add 10.33.0.1/24 dev eth0.311
tc qdisc add dev eth0.311 clsact
tc filter add dev eth0.311 egress protocol ip prio 1 u32 match ip dport 5001 0xffff action skbedit priority 7
tc filter add dev eth0.311 egress protocol ip prio 2 u32 match ip dport 5002 0xffff action skbedit priority 6
tc qdisc replace dev eth0 parent root handle 100: taprio num_tc 3 map 0 0 1 2 0 0 0 0 0 0 0 0 0 0 0 0 queues 1@0 1@1 1@2 base-time 0 sched-entry S 04 125000 sched-entry S 02 125000 sched-entry S 01 250000 flags 2
tc -s qdisc show dev eth0
""".replace("\n+", "\n"), 60)
    qdisc = runner.command("sk", "qbv-qdisc", "tc -s qdisc show dev eth0")
    runner.save("qbv-qdisc.txt", qdisc)
    runner.script("tmds", "qbv-receiver", """set -eu
ip link set eth1 up
ip link add link eth1 name eth1.311 type vlan id 311
ip link set eth1.311 up
sleep 5
ip addr flush dev eth1.311
ip addr add 10.33.0.2/24 dev eth1.311
iperf3 -s -D -B 10.33.0.2 -p 5001
iperf3 -s -D -B 10.33.0.2 -p 5002
tcpdump -i eth1 -w /tmp/tsn-auto-qbv.pcap 'vlan and udp' >/dev/null 2>&1 &
echo $! > /tmp/tsn-auto-qbv-capture.pid
ping -c 2 -W 2 -I eth1.311 10.33.0.1
""".replace("\n+", "\n"))
    runner.script("sk", "qbv-traffic", f"""iperf3 -c 10.33.0.2 -u -b 20M -t {runner.runtime_sec} -p 5001
iperf3 -c 10.33.0.2 -u -b 20M -t {runner.runtime_sec} -p 5002
""", runner.runtime_sec * 3 + 30)
    capture = runner.script("tmds", "qbv-read-capture", """set -eu
kill -INT $(cat /tmp/tsn-auto-qbv-capture.pid) 2>/dev/null || true
sleep 1
printf '%s\\n' '[udp5001]'
tcpdump -r /tmp/tsn-auto-qbv.pcap -n -e -c 1 'vlan and udp port 5001' 2>&1 || true
printf '%s\\n' '[udp5002]'
tcpdump -r /tmp/tsn-auto-qbv.pcap -n -e -c 1 'vlan and udp port 5002' 2>&1 || true
""")
    runner.save("qbv-capture.txt", capture)
    return {"flags_2": "flags 0x2" in qdisc, "pcp7": "vlan 311, p 7" in capture, "pcp6": "vlan 311, p 6" in capture}


def counter_value(text: str, names: tuple[str, ...]) -> int | None:
    for name in names:
        match = re.search(rf"{re.escape(name)}:\s*(\d+)", text)
        if match:
            return int(match.group(1))
    return None


def run_qbu(runner: Runner) -> dict[str, Any]:
    runner.script("sk", "qbu-receiver", """set -eu
ip link set eth1 down
ip link set eth0 down
ethtool -L eth0 tx 4
ethtool --set-priv-flags eth0 p0-rx-ptype-rrobin off
ethtool --set-mm eth0 pmac-enabled on tx-enabled on verify-enabled on verify-time 10 tx-min-frag-size 124
ip link set eth0 up
sleep 8
ip addr add 192.168.107.20/24 dev eth0
iperf3 -s -D -p 5002
iperf3 -s -D -p 5003
""".replace("\n+", "\n"), 60)
    runner.script("tmds", "qbu-sender", """set -eu
ip link set eth0 down
ip link set eth1 down
ethtool -L eth1 tx 4
ethtool --set-priv-flags eth1 p0-rx-ptype-rrobin off
ethtool --set-mm eth1 pmac-enabled on tx-enabled on verify-enabled on verify-time 10 tx-min-frag-size 124
ip link set eth1 up
sleep 8
ip addr add 192.168.107.30/24 dev eth1
tc qdisc replace dev eth1 handle 100: root mqprio num_tc 4 map 0 1 2 3 3 3 3 3 3 3 3 3 3 3 3 3 queues 1@0 1@1 1@2 1@3 hw 1 mode dcb fp P P P E
tc qdisc replace dev eth1 clsact
tc filter add dev eth1 egress protocol ip prio 1 u32 match ip dport 5002 0xffff action skbedit priority 2
tc filter add dev eth1 egress protocol ip prio 2 u32 match ip dport 5003 0xffff action skbedit priority 3
""".replace("\n+", "\n"), 60)
    before_sender = runner.command("tmds", "qbu-sender-before", "ethtool -S eth1; ethtool --include-statistics --show-mm eth1")
    before_receiver = runner.command("sk", "qbu-receiver-before", "ethtool -S eth0; ethtool --include-statistics --show-mm eth0")
    runner.script("tmds", "qbu-traffic", f"""set -eu
iperf3 -c 192.168.107.20 -u -b 200M -l 1472 -t {runner.runtime_sec} -p 5002 &
iperf3 -c 192.168.107.20 -u -b 50M -l 1472 -t {runner.runtime_sec} -p 5003 &
wait
""", runner.runtime_sec * 2 + 30)
    after_sender = runner.command("tmds", "qbu-sender-after", "ethtool -S eth1; ethtool --include-statistics --show-mm eth1")
    after_receiver = runner.command("sk", "qbu-receiver-after", "ethtool -S eth0; ethtool --include-statistics --show-mm eth0")
    runner.save("qbu-sender-before.txt", before_sender)
    runner.save("qbu-receiver-before.txt", before_receiver)
    runner.save("qbu-sender-after.txt", after_sender)
    runner.save("qbu-receiver-after.txt", after_receiver)
    tx_before = counter_value(before_sender, ("MACMergeFragCountTx", "iet_tx_frag"))
    tx_after = counter_value(after_sender, ("MACMergeFragCountTx", "iet_tx_frag"))
    rx_before = counter_value(before_receiver, ("MACMergeFrameAssOkCount", "iet_rx_assembly_ok"))
    rx_after = counter_value(after_receiver, ("MACMergeFrameAssOkCount", "iet_rx_assembly_ok"))
    return {
        "sender_tx_active": "TX active: on" in before_sender,
        "sender_verify_succeeded": "Verification status: SUCCEEDED" in before_sender,
        "sender_fragment_delta": None if tx_before is None or tx_after is None else tx_after - tx_before,
        "receiver_reassembly_delta": None if rx_before is None or rx_after is None else rx_after - rx_before,
    }


def result_pass(feature: str, evidence: dict[str, Any]) -> bool:
    if feature == "gptp":
        return bool(evidence["tmds_slave"])
    if feature in {"dscp-pcp", "qbv"}:
        required = ("pcp7", "pcp6") if feature == "dscp-pcp" else ("flags_2", "pcp7", "pcp6")
        return all(bool(evidence[item]) for item in required)
    if feature == "qbu":
        return (
            evidence["sender_tx_active"]
            and evidence["sender_verify_succeeded"]
            and (evidence["sender_fragment_delta"] or 0) > 0
            and (evidence["receiver_reassembly_delta"] or 0) > 0
        )
    raise AssertionError(feature)


def make_run_dir(feature: str) -> Path:
    timestamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    return LOG_ROOT / f"{timestamp}-{feature}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=int, default=45, help="UART command timeout in seconds")
    parser.add_argument("--runtime-sec", type=int, default=12, help="traffic or ptp observation duration")
    subparsers = parser.add_subparsers(dest="action", required=True)
    preflight_parser = subparsers.add_parser("preflight", help="validate data-port carrier and physical pair mapping")
    preflight_parser.add_argument("--bring-up-links", action="store_true", help="administratively enable data ports before checking")
    baseline_parser = subparsers.add_parser("baseline", help="check or apply the shared-clean-v1 runtime baseline")
    baseline_parser.add_argument("operation", choices=("check", "apply"))
    baseline_parser.add_argument("--execute", action="store_true", help="acknowledge runtime cleanup when applying")
    run_parser = subparsers.add_parser("run", help="run one stateful TSN validation")
    run_parser.add_argument("feature", choices=("gptp", "dscp-pcp", "qbv", "qbu"))
    run_parser.add_argument("--execute", action="store_true", help="acknowledge runtime network and QoS changes")
    run_parser.add_argument("--bring-up-links", action="store_true", help="administratively enable data ports before checking")
    args = parser.parse_args()

    feature = args.action if args.action in {"preflight", "baseline"} else args.feature
    runner = Runner(make_run_dir(feature), args.timeout, args.runtime_sec)
    feature_started = False
    result: dict[str, Any] = {"feature": feature, "pass": False}
    try:
        if args.action == "baseline":
            if args.operation == "apply":
                if not args.execute:
                    raise ValidationError("baseline apply requires --execute")
                apply_baseline(runner)
            baseline = check_baseline(runner)
            result = {"feature": "shared-clean-v1", "pass": True, "baseline": baseline}
        elif args.action == "preflight":
            topology = preflight(runner, args.bring_up_links, prove_pairs=True)
            result = {"feature": "preflight", "pass": True, "topology": topology}
        else:
            topology = preflight(runner, args.bring_up_links, prove_pairs=True)
            baseline = check_baseline(runner)
            if not args.execute:
                raise ValidationError("stateful test requires --execute; preflight and baseline checks were recorded before refusing")
            feature_started = True
            actions = {"gptp": run_gptp, "dscp-pcp": run_dscp_pcp, "qbv": run_qbv, "qbu": run_qbu}
            evidence = actions[args.feature](runner)
            result = {"feature": args.feature, "pass": result_pass(args.feature, evidence), "topology": topology, "baseline": baseline, "evidence": evidence}
    except ValidationError as exc:
        result = {"feature": feature, "pass": False, "error": str(exc)}
    finally:
        if feature_started:
            try:
                apply_baseline(runner)
                result["restored_baseline"] = check_baseline(runner)
            except ValidationError as exc:
                result = {"feature": feature, "pass": False, "error": f"cleanup failed: {exc}"}
    (runner.run_dir / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
