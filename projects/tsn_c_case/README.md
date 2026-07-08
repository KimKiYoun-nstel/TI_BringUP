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
- 현재 최종 결론:
  - `gptp_icssg_switch` donor 기반 Path B remoteproc bring-up 자체는 성공했다.
  - 그러나 최종 fresh-start 검증 기준으로 donor와 같은 bridge-generated gPTP 기능은 성립하지 않았다.
  - 직접 근거는 `port1/2 asCap=0`, `gptp_ascross` 0 hits, downstream `Sync/Follow_Up/Announce` 미성립이다.
- 현재 repo에서 확인된 핵심 자산:
  - 전체 review 문서: `docs/project-review.md`
  - 최종 closure/status 문서: `docs/closure-status.md`
  - 최종 기능 검증 문서: `docs/2026-07-06_gptp-bridge-fresh-start-validation.md`
  - 1차 정리 문서: `docs/phase1-summary.md`
  - U-Boot RM patch: `bsp/u-boot/patches/0005-am64x-rm-cfg-share-icssg1-pktdma-with-main-0-r5-1.patch`
  - Linux DT overlay patch: `bsp/linux/patches/0003-arm64-dts-ti-k3-am642-evm-add-icssg1-r5f-owner-overlay.patch`
  - MCU+ project patch set:
    - `patches/0001-tsn-add-remoteproc-gptp-icssg-project.patch`
    - `patches/0002-tsn-trace-remoteproc-gptp-bridge-path.patch`
  - MCU+ workspace branch: `phase2-tsn-c-case`
  - historical reference diff: `bsp/mcu-plus/patches/0004-am64x-gptp-icssg-linux-remoteproc-pathb-integration-reference.patch`

## 문서

- `docs/project-review.md`: 시작 목표, 진행, 최종 결론, cleanup까지 한 번에 보는 review 문서
- `docs/README.md`: canonical 문서와 archive 문서 구분 안내
- `docs/closure-status.md`: 프로젝트 마감 관점의 최종 상태, 남은 workspace residue, 부트 이미지 연관성
- `docs/2026-07-06_gptp-bridge-fresh-start-validation.md`: 최종 end-to-end 검증과 non-equivalent 결론
- `docs/phase1-summary.md`: Path B bring-up 성공 범위를 고정한 중간 단계 문서
- `docs/resource-ownership-audit.md`: RM ownership root cause와 해결 근거
- `docs/powerclock-trace-result.md`: 초기 power/clock blocker 분석 근거
- `docs/archive/`: 단계별 진행 중 남긴 작업 메모와 중간 판단 기록

## 스크립트

- `board/collect_tmds_c1_baseline.sh`
  - TMDS Linux 상태에서 C1 baseline 수집용 SSH helper

## 현재 판단

- `remoteproc` 적합화와 boot-chain ownership blocker 해소까지는 완료됐다.
- 하지만 donor `gptp_icssg_switch`와 동일 기능의 remoteproc port라고 결론내릴 수는 없다.
- 현재 프로젝트를 닫는 기준 판단은 다음과 같다.

```text
bring-up / task-entry: 성공
boot-chain ownership fix: 성공
donor-equivalent bridge gPTP: 실패
workspace cleanup: 완료
on-board residue cleanup: 완료
```

- 남은 핵심 작업은 새 기능 검증이 아니라 다음 두 가지다.
  1. project 문서/자산 기준선 정리
  2. 필요한 경우 이번 정리 결과를 main repo commit 단위로 묶고, 이후 custom board 작업과 충돌하지 않는지 재점검
