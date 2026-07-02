# AM64x TSN C Case Lab

## 목적

이 프로젝트는 `TMDS64EVM`을 주 대상 보드로 사용해 MCU+ SDK 기반 `ICSSG gPTP bridge / TSN switch` 가능성을 검증하기 위한 작업 구역이다.

핵심 목표는 다음과 같다.

1. `TMDS64EVM`에서 `ICSSG dual-port` 구성이 실제로 가능한지 확인한다.
2. Linux가 `ICSSG Ethernet`을 잡지 않도록 ownership을 분리할 수 있는지 확인한다.
3. `MCU+ SDK gptp_icssg_*` 예제를 빌드해 `R5F firmware` 후보를 확보한다.
4. 해당 firmware를 `remoteproc` 경로로 올릴 수 있는지 분리 검증한다.

## 현재 기준

- 로드맵 원문: `.agents/am64x_c_case_execution_roadmap_plan.md`
- 현재 1차 결론:
  - `gptp_icssg_switch` donor 기반 Path B remoteproc 이식은 성공했다.
  - 외부 end-to-end forwarding/gPTP 검증은 아직 미완료다.
  - 하지만 실보드에서 `Enet/ICSSG init`, `PHY alive`, `link up`, `TSN modules started`, `gPTP task enter`까지는 확인됐다.
- 현재 repo에서 확인된 핵심 자산:
  - 1차 정리 문서: `docs/c6-phase1-summary.md`
  - U-Boot RM patch: `bsp/u-boot/patches/0005-am64x-rm-cfg-share-icssg1-pktdma-with-main-0-r5-1.patch`
  - Linux DT overlay patch: `bsp/linux/patches/0003-arm64-dts-ti-k3-am642-evm-add-icssg1-r5f-owner-overlay.patch`
  - MCU+ integration reference patch: `bsp/mcu-plus/patches/0004-am64x-gptp-icssg-linux-remoteproc-pathb-integration-reference.patch`

## 문서

- `docs/plan.md`: C Case 실행 순서와 현재 우선순위
- `docs/c0-c1-prep.md`: C0/C1 준비 상태, 확정 사실, blocker
- `docs/c0-sdk-example-inventory.md`: MCU+ SDK `gptp_icssg_*` example inventory와 build 결과
- `docs/c6-phase1-summary.md`: 현재까지의 성공 범위, 실제 보드 변경점, patch/provenance 자산, 남은 검증 항목

## 스크립트

- `board/collect_tmds_c1_baseline.sh`
  - TMDS Linux 상태에서 C1 baseline 수집용 SSH helper

## 현재 판단

- `remoteproc` 적합화와 boot-chain ownership blocker 해소까지는 완료됐다.
- 현재 단계는 bring-up 성공 직후의 1차 정리와 후속 검증 준비 단계다.
- 다음 우선순위는 `forwarding/gPTP end-to-end 검증`, `MDIO probe 정합성 재검토`, `temporary override의 장기 채택 경로 정리`다.
