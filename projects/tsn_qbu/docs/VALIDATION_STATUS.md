# AM64x Qbu Clean-Base Validation Status

## 목적

이 문서는 SK-AM64B와 TMDS64EVM에서 수행한 Qbu/IET 검증 작업을 clean baseline부터
현재 상태까지 한 번에 정리하는 canonical closeout이다. 날짜별 시험 원본은 유지하되,
현재 판단은 이 문서를 기준으로 한다.

## 핵심 결론

1. AM64x CPSW Qbu/IET control plane과 actual dataplane은 이 환경에서 동작한다.
   - TMDS `eth1` sender에서 실제 fragment와 SK receiver reassembly를 반복 확인했다.
2. 초기 Pair A official-style 재현에서 `SK eth0 -> TMDS eth1`의 counter가 0이었던 것은
   Qbu 기능 전체의 불능 증거가 아니다.
3. SK sender는 100 Mbps에서 actual Qbu를 수행했다.
4. SK sender의 1 Gbps Qbu가 "HW spec 부족"이라는 결론은 성립하지 않는다.
   - 현재 SK의 단일 CPU userspace generator 조건은 TMDS의 2-core 병렬 generator와
     동일한 packet timing/burst를 만들지 못했다.
   - TMDS도 두 generator process를 CPU 0 하나에 고정하면 fragment가 0이었다.
5. 따라서 현재 우선 과제는 SK 1 Gbps hardware failure를 가정한 수정이 아니라,
   kernel-level generator로 충분한 overlap을 강제하는 검증 환경을 만드는 것이다.

## Clean Baseline

Qbu 시험 전 두 보드에 남아 있던 Qbv/DSCP-PCP 자동 설정을 제거했다.

- SK
  - `br-tsn` 관련 `.netdev`/`.network`를 `.qbu-disabled`로 비활성화했다.
  - data port를 L2-only로 정리했다.
- TMDS
  - `eth1`/`eth2` TSN overlay profile을 `.qbu-disabled`로 비활성화했다.
  - `ti-tsn-dscp-pcp-tmds.service`를 disable했다.
- 공통
  - 대상 CPSW port의 `p0-rx-ptype-rrobin`을 off로 맞췄다.
  - data port의 IP, qdisc, MAC Merge state를 시험 전에 명시적으로 초기화했다.

clean baseline의 정확한 파일 및 idle state는 [baseline.md](baseline.md)를 따른다.
live board는 각 시험 후 runtime state가 남을 수 있으므로, 새 검증 시작 전 이 baseline을
다시 적용해야 한다.

## 검증 기준

다음은 Qbu actual execution의 직접 증거다.

- sender: `MACMergeFragCountTx` 또는 `iet_tx_frag` 증가
- receiver: `MACMergeFragCountRx`, `MACMergeFrameAssOkCount`, 또는
  `iet_rx_assembly_ok` 증가

다음은 control plane/classification 증거일 뿐 actual Qbu 증거는 아니다.

- `ethtool --set-mm` 성공
- `TX active: on`
- `mqprio ... fp ...` 수용
- `tc` filter hit 또는 `tx_pri2`/`tx_pri3` 증가
- MAC Verify `SUCCEEDED`

## 작업 이력과 이슈 처리

### 1. 기존 TSN 설정 간섭

초기 보드는 bridge, VLAN, networkd profile, 자동 TSN 서비스가 남아 있어 결과를 분리할 수
없었다.

- 해결: 위 clean baseline을 적용했다.
- 상태: 해결. 이후 canonical 시험은 plain interface, no VLAN, no netns 기준으로 수행했다.

### 2. TI 공식 예제 조건의 `TX=4` 재현 실패

초기 `ethtool -L <ifname> tx 4`는 `Device or resource busy`로 실패했고 TX queue가 8개로
남았다.

- 원인: 해당 CPSW instance의 다른 port가 up인 상태였다.
  `am65_cpsw_set_channels()`는 `common->usage_count != 0`이면 `-EBUSY`를 반환한다.
- 해결: 같은 CPSW instance의 port를 모두 down한 뒤 대상 port의 TX channel을 4로 변경했다.
- 상태: 해결. SK와 TMDS 모두 `TX=4`를 적용할 수 있다.

### 3. TI official-style Pair A에서 actual counter가 0

Pair A `SK eth0 -> TMDS eth1`에 아래를 적용했다.

- plain interface, no VLAN, no netns
- TX=4
- `mqprio num_tc 4 ... mode dcb ... fp P P P E`
- UDP 5002 -> priority 2/preemptible, 200 Mbps, 1472 bytes
- UDP 5003 -> priority 3/express, 50 Mbps, 1472 bytes
- `tx-min-frag-size 124`

설정 수용, TC 분리, sender priority counter, IET register arm까지 확인됐지만
`MACMergeFragCountTx`와 receiver reassembly counter는 0이었다.

당시 남은 편차는 verify-on이었다.

- SK `eth0`는 verify failure를 보였다.
- TMDS `eth1`는 verify success를 보였다.
- force mode(`verify-enabled off`)에서는 양쪽 `TX active: on`까지 도달했다.

판정:

- "TI official verify-on example을 양쪽 sender에서 완전 재현"은 아직 완료되지 않았다.
- 그러나 이 결과를 AM64x Qbu 전체 failure로 해석하면 안 된다. 다음 sender-direction 시험에서
  actual Qbu가 확인됐다.

### 4. TMDS sender가 동작한 이유

Direction-first 시험에서 TMDS `eth1` sender는 1 Gbps에서 actual Qbu를 반복 수행했다.

- TMDS `eth1 -> SK eth0`: TX fragment `+3329`, SK reassembly `+3328`
- 물리 배선 재확인 후 TMDS `eth1 -> SK eth1`: TX fragment `+9710`, SK reassembly `+9710`

이는 갑자기 기능이 바뀐 것이 아니다. sender direction과 실제 traffic generation timing이
달라진 결과다.

동일 `netperf` 조건에서 확인한 비교:

| Sender condition | TC2 actual rate | TC3 actual rate | `iet_tx_frag` delta |
|---|---:|---:|---:|
| SK eth1, 1 CPU | 약 202 Mbps | 약 16 Mbps | 0 |
| TMDS eth1, 2-core 일반 실행 | 약 418 Mbps | 약 33 Mbps | +509,379 |
| TMDS eth1, 두 sender process를 CPU 0에 pin | 약 243 Mbps | 약 23 Mbps | 0 |

두 보드는 같은 kernel image, 같은 `netperf` command, 같은 packet size, 같은 TC classification을
사용했다. TMDS의 두 sender process를 하나의 CPU에 강제하자 TMDS도 fragment가 0이었다.

판정:

- Qbu fragment는 average requested bitrate가 아니라 preemptible frame의 wire-time 중간에
  express frame이 도착하는 실제 packet timing/burst에 의존한다.
- TMDS 2-core 조건은 이 overlap을 만들었고, SK 1-core userspace generator 조건은 현재
  그 조건을 입증하지 못했다.
- 이것은 SK CPSW/IET hardware failure 또는 SK HW spec 부족의 증거가 아니다.

### 5. SK sender의 상태

SK sender는 여러 CPSW sender path에서 기존 official-style `iperf3` 조건으로 fragment가
0이었다.

- SK `eth0 -> TMDS eth1`: 0
- SK `eth1 -> TMDS eth2`: 0
- SK `eth1 -> TMDS eth1`: 0
- SK에 TMDS와 같은 dirty kernel image를 수동 부팅해도: 0

하지만 양쪽 link를 100 Mbps/full duplex로 강제하고 SK sender에 TC2 80 Mbps + TC3 10 Mbps를
적용하면 actual Qbu가 발생했다.

- SK TX fragment: `+25,130`
- TMDS RX fragment: `+25,130`
- TMDS reassembly OK: `+25,123`

판정:

- SK CPSW MAC Merge/IET TX hardware path는 동작한다.
- 1 Gbps에서 fragment 0은 현재 workload가 overlap을 충분히 강제했는지 입증되지 않아
  hardware issue로 판정할 수 없다.

## MAC Verify의 해석

verify status는 actual Qbu의 pass/fail 조건이 아니다.

- receiver SK가 local verify `FAILED`여도 TMDS sender fragment와 SK reassembly가 발생했다.
- sender SK가 local verify `SUCCEEDED`여도 fragment는 자동으로 발생하지 않았다.
- force mode에서도 actual Qbu는 TMDS sender와 SK 100 Mbps sender에서 확인됐다.

따라서 verify는 link-local handshake 상태로 별도 관리한다. Pair A에서 SK verify failure의
직접 원인은 미해결이나, 그것만으로 sender fragment 0을 설명하지 않는다.

## 현재 상태

| 항목 | 상태 | 근거 |
|---|---|---|
| clean baseline 절차 | 완료 | bridge/overlay/service 간섭 제거 및 L2-only 기준 고정 |
| TX=4 설정 | 해결 | 같은 CPSW instance port down 후 적용 가능 |
| TMDS CPSW sender actual Qbu, 1 Gbps | 완료 | 두 SK receiver port에서 fragment/reassembly 반복 확인 |
| SK CPSW sender actual Qbu, 100 Mbps | 완료 | TX/RX fragment 및 reassembly 확인 |
| SK CPSW sender actual Qbu, 1 Gbps | 미판정 | current userspace generator로 sufficient overlap 미입증 |
| Pair A strict verify-on 재현 | 미해결 | SK verify failure 존재 |
| ICSSG sender path | 미검증 | TMDS eth2 receiver 비교만 수행 |

## 재현성 상태

현재 repo에는 clean rootfs baseline overlay, canonical TMDS sender procedure, kernel/DTB hash,
그리고 historical counter evidence ledger가 관리된다. Qbu feature에는 custom image delta가
필요하지 않으며 runtime 설정으로 검증한다. historical certificate artifact는 `-dirty` Image지만,
TI SDK prebuilt image에서의 actual-Qbu certificate가 필요할 때만 별도 재검증한다. close 조건은
[CLOSURE_CHECKLIST.md](CLOSURE_CHECKLIST.md), artifact identity는
[PROVENANCE.md](PROVENANCE.md), 실행 절차는 [REPRODUCTION.md](REPRODUCTION.md)를 따른다.

## 다음 작업

1. SK kernel build에 `CONFIG_NET_PKTGEN=y` 또는 module을 포함한다.
2. clean baseline에서 SK eth1 sender, TMDS eth1 receiver를 준비한다.
3. TC2는 1472-byte preemptible traffic을 actual 850~950 Mbps로 유지한다.
4. TC3에는 64~256-byte high-PPS express traffic을 동시에 넣는다.
5. `tx_pri2_bcnt`, `tx_pri3_bcnt`, packet delta, `iet_tx_frag`, receiver assembly counter를
   같은 30-second window에서 수집한다.
6. 그 조건에서도 SK fragment가 0일 때만 1 Gbps CPSW/IET state, driver, PHY/RGMII를
   원인 후보로 올린다.

## 관련 기록

- [baseline.md](baseline.md): clean baseline과 복원 기준
- [history/2026-07-08_pairA_official_reproduction_result.md](history/2026-07-08_pairA_official_reproduction_result.md): Pair A official-style 원본 결과
- [history/2026-07-09_direction_first_d1_d2_result.md](history/2026-07-09_direction_first_d1_d2_result.md): sender direction 전환 결과
- [history/2026-07-09_rewired_pair_c_result.md](history/2026-07-09_rewired_pair_c_result.md): 물리 배선 재확인 및 TMDS sender 재현
- [history/sk_cpsw_tx_fragmentation_root_cause.md](history/sk_cpsw_tx_fragmentation_root_cause.md): register, kernel provenance, rate 비교 상세
- [REPRODUCTION.md](REPRODUCTION.md): canonical validation 실행 절차
- [PROVENANCE.md](PROVENANCE.md): kernel/DTB/rootfs provenance
- [CLOSURE_CHECKLIST.md](CLOSURE_CHECKLIST.md): project close 조건
- [../logs/2026-07-13_validation_evidence_ledger.md](../logs/2026-07-13_validation_evidence_ledger.md): counter evidence ledger
