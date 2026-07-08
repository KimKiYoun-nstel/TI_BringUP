# AM64x TSN C Case Project Review

## 한 줄 요약

`TMDS64EVM`에서 donor `gptp_icssg_switch` 예제를 Linux `remoteproc` 경로로 bring-up하는 데는 성공했지만,
최종적으로 donor와 같은 bridge-generated gPTP 기능은 성립하지 않았다.

## 이 프로젝트를 왜 했나

이 프로젝트의 출발점은 다음 질문이었다.

1. `TMDS64EVM`에서 `ICSSG1 dual-port`를 Linux 기본 경로 대신 R5F firmware가 소유하게 만들 수 있는가?
2. MCU+ SDK의 `gptp_icssg_switch` 예제를 Linux `remoteproc`로 올릴 수 있는가?
3. 그렇게 올린 firmware가 donor 예제와 같은 bridge-generated gPTP 기능을 실제로 수행하는가?

즉 단순히 firmware를 `running` 상태로 만드는 것이 아니라,
**donor 예제의 의도된 기능까지 Linux-hosted remoteproc 구조에서 성립하는지**를 확인하는 것이 목적이었다.

## 시작 상태

초기에는 다음 전제가 있었다.

- Linux가 기본적으로 `ICSSG Ethernet` 경로를 일부 소유하고 있었다.
- donor 예제는 bare-metal/RTOS 쪽 ownership 가정을 강하게 가진다.
- TMDS 실보드에서는 그대로는 `Enet_open()` / DMA / clock / ownership blocker가 연속적으로 발생했다.

따라서 이 프로젝트는 크게 세 단계로 진행됐다.

1. Linux/boot-chain ownership 분리
2. donor 예제의 remoteproc bring-up 성립
3. donor-equivalent 기능 검증

## 중간 성과: bring-up 성공

중간 단계에서 확보한 가장 중요한 성과는 다음이다.

- Path B `remoteproc-ready scaffold` 기반 이식 성공
- `ICSSG_1 PKTDMA` RM ownership blocker 해소
- 실보드에서 아래 runtime 진입 확인

```text
Mdio_open
Open MAC port 1
Open MAC port 2
PHY 3 is alive
PHY 15 is alive
default RX flow started
TSN modules started
TSN and gPTP tasks started
netdev_count=2
```

이 단계까지는 분명히 성공이다.

즉 이 프로젝트는

- `remoteproc load`
- firmware bootstrap
- Enet/ICSSG init
- PHY/link up
- TSN/gPTP task entry

까지는 실제로 올라갔다.

이 범위는 `phase1-summary.md`가 가장 잘 설명한다.

## 무엇을 바꿨나

핵심 변경 축은 3개였다.

### 1. U-Boot / boot-chain RM

- `ICSSG_1 PKTDMA` 자원을 baseline `A53_2 (12)`에 남기면서
- 동일 range를 `MAIN_0_R5_1 (36)`에도 배정

자산:

- patch: `bsp/u-boot/patches/0005-am64x-rm-cfg-share-icssg1-pktdma-with-main-0-r5-1.patch`

### 2. Linux ownership 분리

- `cpsw_port2` disable
- `mdio_mux_1` disable
- `icssg1_eth` disable
- `/aliases`의 `ethernet1`, `ethernet2` 삭제

자산:

- patch: `bsp/linux/patches/0003-arm64-dts-ti-k3-am642-evm-add-icssg1-r5f-owner-overlay.patch`

중요:

- 실보드 검증의 주 경로는 permanent DT overlay가 아니라
  U-Boot temporary `fdt set`였다.

### 3. MCU+ remoteproc path

- custom CCS project 구성
- remoteproc bootstrap wrapper
- clock/trace/TSN stack adaptation
- 후반부에는 local git seed repo + branch 구조로 재정리

현재 canonical 자산:

- `projects/tsn_c_case/patches/0001-tsn-add-remoteproc-gptp-icssg-project.patch`
- `projects/tsn_c_case/patches/0002-tsn-trace-remoteproc-gptp-bridge-path.patch`
- workspace branch: `phase2-tsn-c-case`

## 최종 검증 질문

최종적으로 확인하고 싶었던 topology는 이것이었다.

```text
SK eth0 (GM/master 후보)
  -> TMDS ICSSG port1
  -> TMDS gPTP bridge / switch path
  -> TMDS ICSSG port2
  -> SK eth1 (slave 후보)
```

즉 donor 예제가 의도한 downstream `Sync/Follow_Up/Announce`가 실제로 bridge-generated egress로 나오는지 확인하는 것이었다.

## 최종 결론

최종 결론은 명확하다.

- `gptp_icssg_switch` donor 기반 Path B Linux remoteproc bring-up 자체는 성공했다.
- 하지만 donor와 같은 bridge-generated gPTP 기능은 성립하지 않았다.
- 따라서 현재 이식은 donor와 **behaviorally equivalent 하지 않다.**

직접 근거:

- `port1 asCap=0`
- `port2 asCap=0`
- `gptp_ascross` 0 hits
- downstream `Sync/Follow_Up/Announce` 미성립
- SK `eth1`는 끝까지 self-GM

핵심 기술 해석:

- 직접 blocker는 `asCapableAcrossDomains` 미성립
- 즉 문제는 단순 forwarding failure가 아니라,
  그보다 앞단의 gPTP prerequisite gate가 열리지 않는 데 있다.

이 최종 판정은 `2026-07-06_gptp-bridge-fresh-start-validation.md`가 가장 상세하게 담고 있다.

## 이 프로젝트의 산출물은 무엇인가

이 프로젝트는 두 종류의 산출물을 남겼다.

### 1. 재현 자산

- U-Boot RM patch
- Linux ownership overlay patch
- MCU+ project patch set
- 관련 provenance 문서

### 2. 판단 자산

- bring-up 성공 범위를 설명하는 문서
- root-cause 추적 문서
- 최종 non-equivalent 결론 문서
- cleanup 및 residue 정리 문서

## 어떤 문서를 봐야 하나

프로젝트 전체를 한 번에 이해하려면 이 문서를 먼저 본다.

그 다음 목적별로 아래를 본다.

- `phase1-summary.md`
  - bring-up이 어디까지 성공했는지
- `2026-07-06_gptp-bridge-fresh-start-validation.md`
  - 왜 donor-equivalent 기능이 실패라고 결론났는지
- `closure-status.md`
  - workspace, boot image, on-board cleanup까지 어떻게 닫았는지
- `resource-ownership-audit.md`
  - ownership/RM 관점의 중간 root-cause 추적
- `powerclock-trace-result.md`
  - 초반 `PowerClock_init()` blocker를 어떻게 돌파했는지

## 정리 후 상태

현재 이 프로젝트는 다음 기준으로 닫혔다.

```text
bring-up / task-entry: 성공
boot-chain ownership fix: 성공
donor-equivalent bridge gPTP: 실패
workspace cleanup: 완료
on-board residue cleanup: 완료
```

즉 이 프로젝트는

- "문제가 해결되었다"가 아니라
- "donor example은 현재 remoteproc 이식 상태에서 동일 기능이 아니다"

를 증거와 함께 확정한 프로젝트다.

## 후속 작업에 주는 의미

이 프로젝트 이후에는 두 가지 선택지만 남는다.

1. `gptp_icssg_switch`를 donor-equivalent 예제로 계속 밀지 않는다.
2. 정말 같은 기능이 필요하다면
   `md_pdelay_req_sm` / `asCapableAcrossDomains` 경로를 포함한 deeper adaptation을 별도 프로젝트로 다시 연다.

현재 상태에서 C Case는 **검증/정리 완료된 closeout project**로 보는 것이 맞다.
