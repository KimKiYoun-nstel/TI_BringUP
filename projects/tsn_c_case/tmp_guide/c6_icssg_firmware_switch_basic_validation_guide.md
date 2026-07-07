# C6 ICSSG Firmware Switch 기본 검증 가이드

## 목적

TMDS64EVM에서 Linux `remoteproc`로 실행 중인 R5F `gptp_icssg` 기반 firmware가 ICSSG `eth1/eth2`를 실제 switch 형태로 제어하는지 단계적으로 확인한다.

이번 단계의 목표는 **gPTP/Qbv 검증이 아니다.**  
먼저 firmware가 ICSSG 두 포트를 직접 제어하고, SK 보드와의 기존 직결 2-line 환경에서 기본 switch 동작이 가능한지 확인한다.

---

## 검증 구성

```text
SK-AM64B CPSW port A  <---->  TMDS64EVM ICSSG eth1
SK-AM64B CPSW port B  <---->  TMDS64EVM ICSSG eth2

TMDS A53 Linux:
  - remoteproc로 R5F firmware load/start
  - ICSSG Linux netdev는 사용하지 않음

TMDS R5F firmware:
  - ICSSG switch mode
  - eth1/eth2 PHY/MDIO/port 제어
  - packet forwarding 담당

SK Linux:
  - 기존 CPSW 기반 endpoint/traffic generator 역할
  - 변경 최소화
```

---

## 진행 원칙

1. 문제가 생기면 그 단계에서 멈춘다.
2. gPTP/Qbv로 넘어가지 않는다.
3. TMDS Linux에서 ICSSG `eth1/eth2`가 netdev로 안 보이는 것은 정상일 수 있다.
4. TMDS 내부 ICSSG 상태는 firmware trace/counter로 본다.
5. packet 관찰은 SK 쪽 `tcpdump` 중심으로 한다.

---

## Step 0. TMDS remoteproc / ownership 확인

TMDS에서 확인:

```bash
ip -br link

for r in /sys/class/remoteproc/remoteproc*; do
  echo "----- $r -----"
  cat "$r/name" 2>/dev/null
  cat "$r/firmware" 2>/dev/null
  cat "$r/state" 2>/dev/null
done

dmesg | grep -iE 'remoteproc|r5f|icssg|prueth|pruss|mdio|phy|firmware' | tail -n 200
```

성공 조건:

```text
- R5F remoteproc state = running
- Linux icssg-prueth가 TMDS eth1/eth2를 소유하지 않음
- ICSSG ownership 충돌 로그 없음
```

실패 시:

```text
- DT에서 ICSSG Ethernet probe disable 상태 재확인
- firmware 이름 / remoteproc target core 확인
- dmesg의 carveout/resource_table 에러 확인
```

---

## Step 1. Firmware ICSSG switch 초기화 확인

TMDS에서 remoteproc trace 확인:

```bash
find /sys/kernel/debug/remoteproc -maxdepth 3 -type f -name 'trace*' -print
cat /sys/kernel/debug/remoteproc/remoteprocX/trace0
```

firmware trace에서 최소 확인할 것:

```text
- firmware boot done
- mode = ICSSG switch
- ICSSG instance 확인
- port0 / port1 enable
- MDIO init done
- PHY0 / PHY1 detect
- PRU/RTU/TX_PRU firmware loaded
- switch open/init done
```

성공 조건:

```text
- switch mode로 2개 port 초기화 완료
- trace상 fatal/assert 없음
```

실패 시:

```text
- firmware bootstrap / Board_driversOpen / Enet open 단계 trace 확인
- PHY address / MDIO / ICSSG instance 설정 확인
- 필요 시 firmware trace point 추가 후 재검증
```

---

## Step 2. SK 양쪽 포트 link 확인

SK에서 두 CPSW 포트 확인:

```bash
ip -br link
ethtool <sk_if_a>
ethtool <sk_if_b>
```

TMDS firmware trace에서도 link state 확인:

```text
[PORT] port0 link up
[PORT] port1 link up
speed / duplex 확인 가능하면 기록
```

성공 조건:

```text
- SK 양쪽 interface link up
- TMDS firmware에서도 양쪽 port link up 감지
```

실패 시:

```text
- 케이블/포트 매핑 확인
- PHY detect 여부 확인
- firmware가 link polling 또는 callback을 수행하는지 확인
```

---

## Step 3. 기본 L2 forwarding 확인

SK에서 두 포트에 수동 IP 설정:

```bash
ip addr flush dev <sk_if_a>
ip addr flush dev <sk_if_b>

ip addr add 192.168.100.1/24 dev <sk_if_a>
ip addr add 192.168.100.2/24 dev <sk_if_b>

ip link set <sk_if_a> up
ip link set <sk_if_b> up
```

한 터미널에서 packet 관찰:

```bash
tcpdump -i <sk_if_a> -e -nn arp or icmp
```

다른 터미널에서:

```bash
tcpdump -i <sk_if_b> -e -nn arp or icmp
```

ping 수행:

```bash
ping -I <sk_if_a> 192.168.100.2
ping -I <sk_if_b> 192.168.100.1
```

성공 조건:

```text
- ARP request/reply가 반대편 포트에서 보임
- ICMP echo/reply가 양방향으로 통과
- TMDS firmware RX/TX/forward counter 증가
```

실패 시:

```text
- switch mode인지 dualmac mode인지 재확인
- forwarding/FDB/host port 설정 확인
- firmware counter가 RX까지만 증가하는지, TX까지 증가하는지 분리 확인
```

---

## Step 4. Broadcast / unknown unicast 확인

SK에서 ARP cache 삭제 후 재시도:

```bash
ip neigh flush dev <sk_if_a>
ip neigh flush dev <sk_if_b>
ping -I <sk_if_a> 192.168.100.2 -c 3
```

확인할 것:

```text
- broadcast ARP가 반대편으로 flood 되는가
- reply 이후 unicast forwarding이 되는가
- firmware FDB 또는 forwarding counter 변화가 있는가
```

성공 조건:

```text
- broadcast / unknown unicast / learned unicast의 기본 흐름 확인
```

---

## Step 5. VLAN/PCP 보존 여부 확인

이 단계는 gPTP/Qbv 전의 기본 TSN 준비 검증이다.

SK에서 VLAN interface 생성:

```bash
ip link add link <sk_if_a> name <sk_if_a>.10 type vlan id 10 egress-qos-map 0:3
ip link add link <sk_if_b> name <sk_if_b>.10 type vlan id 10

ip addr add 192.168.10.1/24 dev <sk_if_a>.10
ip addr add 192.168.10.2/24 dev <sk_if_b>.10

ip link set <sk_if_a>.10 up
ip link set <sk_if_b>.10 up
```

관찰:

```bash
tcpdump -i <sk_if_b> -e -nn vlan
ping -I <sk_if_a>.10 192.168.10.2
```

성공 조건:

```text
- VLAN tag가 반대편에서 보임
- PCP 값이 보존됨
- VLAN traffic도 forwarding 됨
```

실패 시:

```text
- firmware switch config의 VLAN 처리 정책 확인
- tag strip/drop 여부 확인
- 필요 시 firmware에 VLAN/PCP trace/counter 추가
```

---

## Step 6. 결과 정리 기준

각 단계 결과를 아래 형식으로 기록한다.

```text
Step:
결과: PASS / FAIL / PARTIAL
근거 로그:
- SK command output
- TMDS remoteproc trace
- firmware counter
판단:
다음 조치:
```

최종적으로 아래를 판단한다.

```text
- TMDS R5F firmware가 ICSSG eth1/eth2를 직접 제어하는가
- ICSSG switch mode로 2-port forwarding이 되는가
- Linux CPSW tool 방식 없이 firmware 설정만으로 기본 switch 동작이 되는가
- gPTP 검증으로 넘어갈 수 있는가
```

---

## 다음 단계 진입 조건

아래가 모두 PASS일 때만 gPTP 검증으로 넘어간다.

```text
- remoteproc running
- ICSSG switch firmware init done
- SK 양쪽 link up
- ARP/ICMP L2 forwarding PASS
- VLAN/PCP preservation 기본 확인
```

이 조건 전에는 gPTP/Qbv 문제를 보지 않는다.
