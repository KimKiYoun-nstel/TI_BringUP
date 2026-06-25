# SK-AM64B R5F Early Boot Project Asset Map

## 목적

이 문서는 이 프로젝트가 어떤 정보를 어디까지 관리해야 하는지,
그리고 `source build bootstrap chain`과 `deploy/verification chain`을 어떻게 구분하는지 고정한다.

## 프로젝트가 관리해야 하는 7개 축

### 1. 작업 내용

- `docs/plan.md`
- `docs/gates.md`
- `docs/communication-plan.md`

### 2. 작업 결과

- `docs/bringup-logs/2026-06-11_SK-AM64B_sbl-ospi-linux-lp4-first-success.md`
- `docs/bringup-logs/2026-06-12_SK-AM64B_sbl-ospi-linux-lp4-dual-boot-success.md`
- `docs/bringup-logs/2026-06-24_SK-AM64B_sbl-ospi-linux-local-fullchain-success.md`
- `projects/sk-am64b-r5f-early-boot/logs/2026-06-24_sbl-ospi-linux-local-fullchain-clean-canonical-uart.log`

### 3. 보드 반영 patch 이력

- `bsp/mcu-plus/patches/0002-am64x-sbl-ospi-linux-keep-lp4-dual-boot-workspace-base.patch`
- `bsp/mcu-plus/patches/0003-am64x-linuxappimagegen-pyelftools-compat.patch`
- `bsp/mcu-plus/patches/series`

### 4. clean workspace 기준 source build to output 생성 chain

이 축은 두 단계로 나눠서 본다.

#### A. source bootstrap chain

목적:

```text
workspace source tree를 기준으로 partial build output을 다시 만들 수 있게 하는 것
```

현재 project에서 직접 다루는 항목:

- MCU+ `sbl_ospi_linux` SBL source build
- current project R5F firmware source build
- R5F multicore appimage 생성
- linux appimage 생성 helper

현재 helper:

- `tools/build/bootstrap-sk-am64b-sbl-ospi-linux-local-fullchain.sh`
- `tools/prepare/apply-mcu-plus-sk-am64b-sbl-ospi-linux-local-fullchain.sh`
- `tools/build/build-sk-am64b-sbl-ospi-linux-local-fullchain.sh`
- `tools/build/build-mcu-plus-example.sh`
- `tools/build/build-r5f-early-boot-app.sh`
- `tools/build/gen-r5f-multicore-appimage.sh`
- `tools/build/gen-linux-appimage-for-sbl.sh`

현재 bootstrap chain에서 아직 외부 partial output을 전제로 두는 항목:

- TF-A `bl31.bin`
- OP-TEE `tee-pager_v2.bin`
- U-Boot A53 chain (`u-boot-spl.bin`, `u-boot.img`)

즉 현재는

```text
source bootstrap chain이 codified 되어 있지만,
TF-A / OP-TEE / U-Boot A53 source bootstrap 실행은 workspace cleanliness 조건에 영향을 받는다.
```

상세 문서:

- `docs/source-bootstrap-chain.md`

#### B. deploy image assembly chain

목적:

```text
partial build output을 재사용해서 보드 deploy용 최종 4-image set을 만든다.
```

현재 canonical final set:

- `out/sk-am64b-sbl-ospi-linux-local-fullchain/`

flash profile:

- `bsp/mcu-plus/configs/sbl_ospi_linux_sk-am64b_local-fullchain.cfg`

### 5. 4의 결과를 local로 관리

partial/local output:

- `out/sk-am64b-r5f-early-boot/`
- `out/r5f-early-boot/linux-appimage-build-local-fullchain/`
- `out/u-boot-local-a53chain/`

final deploy set:

- `out/sk-am64b-sbl-ospi-linux-local-fullchain/`
- `tftp/am64x-sbl-ospi-local-fullchain-canonical/`

### 6. 5의 이미지로 보드 deploy 과정

- Linux fast path write / readback 검증
- 필요 시 UART uniflash 경로

참조:

- `docs/phase2-uart-uniflash-runbook.md`
- `docs/sbl-ospi-linux-local-fullchain-profile.md`

### 7. 검증 결과 방법 및 프로젝트 기능 정리 문서

- `docs/sbl-ospi-linux-local-fullchain-profile.md`
- `docs/gates.md`
- `docs/m1-shm-checker-attempt.md`
- `docs/heartbeat-shm-abi.md`
- raw UART boot log
  - `projects/sk-am64b-r5f-early-boot/logs/2026-06-24_sbl-ospi-linux-local-fullchain-clean-canonical-uart.log`

## 핵심 구분

이 프로젝트에서 가장 중요한 구분은 다음이다.

```text
A. source bootstrap chain
  = source tree -> partial build output

B. deploy image assembly chain
  = partial build output -> final flash image set -> board deploy/verify
```

이 둘을 섞어 쓰면 다음 문제가 생긴다.

- build script가 실제로 무엇을 생성하는지 흐려짐
- workspace 중간 산출물과 final deploy set 경계가 흐려짐
- 다른 host에서 repo만 보고 재현할 때 무엇이 source prerequisite이고 무엇이 reusable output인지 불명확해짐

따라서 현재 project의 canonical surface에서는 항상 이 두 chain을 분리해서 설명해야 한다.
