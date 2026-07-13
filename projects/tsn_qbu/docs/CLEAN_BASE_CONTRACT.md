# Qbu Clean Base And Minimum Board Contract

## 목적

이 문서는 Qbu 검증을 시작할 수 있는 최소 보드 상태를 정의한다. historical validation
artifact와 clean managed base를 혼동하지 않는다.

## 결론

Qbu 기능을 사용하기 위해 관리된 kernel source patch, DTS/DTB patch, U-Boot patch는 없다.
Qbu 시험에서 필요한 것은 기존 AM64x CPSW IET/MM kernel capability와 runtime configuration이다.

Qbu가 남긴 persistent 변경은 rootfs network policy뿐이다.

- 이전 Qbv/DSCP-PCP 자동 profile과 service를 비활성화
- Qbu data port를 IP 없는 L2-only default로 고정

이 cleanup은 Qbu hardware feature의 필수 조건이 아니라, 이전 실험의 자동 설정이 새 시험을
덮어쓰지 않게 하는 isolation 조건이다.

## Kernel And DTB Contract

### Clean Managed Base

| 항목 | 기준 |
|---|---|
| Linux source | `c214492085504176b9c252a7175e4e60b4b442af` |
| managed Qbu kernel patch | 없음 |
| managed Qbu DTS/DTB patch | 없음 |
| managed Qbu bootloader change | 없음 |
| required driver | CPSW `am65-cpsw-nuss` with ethtool MM/IET and mqprio fp support |

다음은 Qbu clean base에서 **배제**한다.

- R5F ownership/ICSSG disable overlay
- USB-root rehearsal DTB
- 이전 TSN DSCP/PCP rootfs overlay의 auto-apply service

### Historical Certificate Artifact

historical actual-Qbu certificate는 `6.18.13-ti-00778-gc21449208550-dirty` Image에서
얻었다. Image/DTB hash는 [PROVENANCE.md](PROVENANCE.md)에 있지만 source diff가 없다.

따라서 current repository는 다음 두 상태를 구분한다.

1. **clean managed base**: source commit과 Qbu patch absence가 명확한 출발점
2. **historical certificate artifact**: counter evidence는 유효하지만 source rebuild 재현은 불가

historical artifact의 source diff는 Qbu feature requirement로 취급하지 않는다. Qbu에는
managed image delta가 없으며, SDK가 제공하는 CPSW IET/MM capability와 runtime configuration을
사용한다.

### New Image Requirement

Qbu 설정 자체를 위해 새 kernel/DTB/rootfs image가 필요한 것은 아니다. managed Qbu source
patch도 없으며, existing CPSW IET/MM capability를 runtime command로 사용한다.

TI SDK prebuilt image에서의 actual-Qbu certificate는 이 프로젝트에서 아직 별도로 취득하지
않았다. 따라서 "TI SDK prebuilt에서 조건부 Qbu가 가능할 것으로 예상된다"와
"TI SDK prebuilt에서 actual counter로 검증됐다"는 구분한다. 후자의 주장이 필요하면
prebuilt image에서 `REPRODUCTION.md`를 1회 실행하면 된다.

## Persistent Rootfs Contract

다음 overlay script가 유일한 Qbu persistent rootfs policy다.

| Board | Overlay script |
|---|---|
| SK-AM64B | `rootfs/overlays/sk-am64b-qbu-clean-baseline/usr/local/sbin/qbu-clean-baseline-sk.sh` |
| TMDS64EVM | `rootfs/overlays/tmds64evm-qbu-clean-baseline/usr/local/sbin/qbu-clean-baseline-tmds.sh` |

script 적용 결과:

- legacy TSN networkd file은 `.qbu-disabled` suffix로 보관
- SK `eth0`, `eth1`와 TMDS `eth1`, `eth2`는 L2-only profile
- TMDS `ti-tsn-dscp-pcp-tmds.service`는 disabled
- Qbu data port에는 persistent IP, bridge, mqprio, MAC Merge enable을 남기지 않음

script 적용 후 reboot하고 다음 idle state를 확인한다.

```text
data port: no IPv4 address
qdisc:     mq + pfifo_fast
MM:        pMAC off, TX off
bridge:    absent
```

2026-07-13에 이 runtime reset을 실제 보드에 적용한 evidence는
`../logs/2026-07-13_clean_runtime_baseline.md`에 보관한다.

## Physical Connection Contract

현재 확인된 배선은 다음이다.

```text
SK eth1 <-> TMDS eth1    canonical CPSW <-> CPSW path
SK eth0 <-> TMDS eth2    comparative CPSW <-> ICSSG path
TMDS eth0                control only
SK control                UART
```

canonical actual-Qbu certificate는 `TMDS eth1 -> SK eth1` 방향이다.

## Runtime Minimum Contract

runtime setting은 persistent image policy가 아니다. 각 run에서 clean idle state 위에 적용하고,
run 종료 후 reset 또는 reboot한다.

1. 대상 CPSW instance의 다른 port를 down한다.
2. sender/receiver target port를 down한 뒤 `ethtool -L <port> tx 4`를 적용한다.
3. `p0-rx-ptype-rrobin off`를 적용한다.
4. MAC Merge, mqprio, filter, test IP를 적용한다.
5. traffic 전후 counter delta를 수집한다.
6. run 종료 후 IP/qdisc/filter/MM state를 제거하거나 clean baseline으로 reboot한다.

canonical TMDS sender runtime command와 pass/fail rule은 [REPRODUCTION.md](REPRODUCTION.md)를
따른다.

## Acceptance Rule

Qbu pass는 sender와 receiver의 hardware counter delta를 함께 요구한다.

- sender `MACMergeFragCountTx` 또는 `iet_tx_frag` > 0
- receiver `MACMergeFragCountRx`와 `MACMergeFrameAssOkCount` 또는
  `iet_rx_assembly_ok` > 0
- TC2/TC3 traffic and classification counter 증가
- error counter가 assembly success보다 지배적으로 증가하지 않음

verify result, `TX active`, `mqprio` 수용은 configuration validity check이며 actual Qbu pass
증거를 대체하지 않는다.
