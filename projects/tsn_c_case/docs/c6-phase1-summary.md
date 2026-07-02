# AM64x TSN C Case Phase 1 Summary

## 목적

`TMDS64EVM` 기준 `gptp_icssg_switch` donor 예제를 Linux `remoteproc` 경로로 이식한 현재 상태를 1차 고정한다.

이 문서는 다음을 함께 정리한다.

1. 이식 성공 범위
2. 아직 검증하지 못한 범위
3. 실제 보드에 영향을 준 변경점
4. repo에 흡수한 patch / provenance 자산
5. 다음 검증 제안

## 1차 결론

### 확정

- Path B `remoteproc-ready scaffold` 기반 이식은 성공했다.
- `gptp_icssg_switch` donor 예제는 `remoteproc` 환경에서 최소한 다음 단계까지 실제로 동작했다.

```text
A remoteproc load
B firmware bootstrap
C Enet/ICSSG init
D MDIO open / PHY alive / link up
E TSN module start
F gPTP task entry
```

- 즉 현재 firmware는 단순히 `running` 상태만 되는 것이 아니라, 기존 `gptp_icssg` 예제가 기대하던 핵심 모듈 기동 수준까지는 올라왔다.

### 아직 미완료

- 외부 traffic forwarding 검증
- 실제 gPTP peer와의 sync 품질 검증
- 반복 reboot 회귀 검증
- `MDIO/PHY ownership` 장기 정책 확정
- `temporary U-Boot fdt set` 경로를 정식 boot path로 바꿀지 여부

따라서 현재 판정은 다음과 같다.

```text
이식: 성공
예제 내부 모듈 기동: 확인
외부 기능 검증: 미완료
```

## 실보드에서 확인한 핵심 증거

대표 trace:

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
MAC Port 1/2 link up
domain=0, offset=0nsec, hw-adjrate=0ppb
```

이 시점에서 다음 두 가지는 확정으로 본다.

1. `Enet_open failed` / `EnetUdma_openRxCh` blocker는 해소됐다.
2. `gptp_icssg_switch` donor의 핵심 runtime stack이 실제로 진입했다.

## 실제 보드 변경점 정리

### Bootloader

필수 변경:

- `ICSSG_1 PKTDMA` resource를 baseline `A53_2 (12)` 유지 상태로 두고,
- 동일 range를 `MAIN_0_R5_1 (36)`에도 추가 배정

이유:

- Path B firmware의 PM/RM/UDMA request는 non-secure host `36`으로 나간다.
- baseline Linux `icssg-prueth` 경로도 유지해야 한다.

repo 자산:

- patch: `bsp/u-boot/patches/0005-am64x-rm-cfg-share-icssg1-pktdma-with-main-0-r5-1.patch`
- provenance: `logs/provenance/u-boot/2026-07-02_tmds64evm_tsn-c-case_rm-cfg-main-r5-1.md`

실보드 적용 artifact:

- `tiboot3.bin`
- `tispl.bin`
- `u-boot.img`

### Kernel code

- 현재까지 **커널 C 코드 변경은 없다.**

### DTB / overlay

검증 중 사용한 ownership 분리 내용:

- `cpsw_port2` disable
- `mdio_mux_1` disable
- `icssg1_eth` disable
- `/aliases`의 `ethernet1`, `ethernet2` 삭제

중요:

- 실보드 검증은 기본적으로 U-Boot temporary `fdt set`로 진행했다.
- 즉 현재 검증 성공 경로는 **DTB를 영구 교체하지 않아도 재현 가능**하다.
- 다만 동일 변경을 정식 DT overlay로 재적용할 수 있도록 patch를 repo에 승격했다.

repo 자산:

- patch: `bsp/linux/patches/0003-arm64-dts-ti-k3-am642-evm-add-icssg1-r5f-owner-overlay.patch`
- provenance: `logs/provenance/linux/2026-07-02_tmds64evm_tsn-c-case_icssg1-r5f-owner-overlay.md`

### MCU+ firmware integration

repo 자산:

- patch reference: `bsp/mcu-plus/patches/0004-am64x-gptp-icssg-linux-remoteproc-pathb-integration-reference.patch`
- provenance: `logs/provenance/mcu-plus/2026-07-02_tmds64evm_tsn-c-case_pathb_remoteproc.md`

주의:

- 이 MCU+ patch는 현재 `git am` 대상의 clean mailbox patch가 아니라,
- scaffold와 donor를 합친 Path B 통합 참조 diff를 정리한 reference patch다.

즉 현재 단계에서는 다음 용도로 본다.

1. workspace 변경 보존
2. 이후 clean replay patch로 재정리할 때 기준선 제공

## repo에 흡수한 재현 자산

### Patch

- `bsp/u-boot/patches/0005-am64x-rm-cfg-share-icssg1-pktdma-with-main-0-r5-1.patch`
- `bsp/linux/patches/0003-arm64-dts-ti-k3-am642-evm-add-icssg1-r5f-owner-overlay.patch`
- `bsp/mcu-plus/patches/0004-am64x-gptp-icssg-linux-remoteproc-pathb-integration-reference.patch`

### Provenance

- `logs/provenance/u-boot/2026-07-02_tmds64evm_tsn-c-case_rm-cfg-main-r5-1.md`
- `logs/provenance/linux/2026-07-02_tmds64evm_tsn-c-case_icssg1-r5f-owner-overlay.md`
- `logs/provenance/mcu-plus/2026-07-02_tmds64evm_tsn-c-case_pathb_remoteproc.md`

## 정리된 불필요 자산

- `projects/tsn_c_case/tmp_guide/c5_core_clock_ownership_verification_guide.md`
  - 임시 작업 가이드였고, 현재는 결과 문서와 patch/provenance 자산으로 대체했다.
- `projects/tsn_c_case/logs/2026-07-01_pathb_integration_reference.diff`
  - `bsp/mcu-plus/patches/0004-...patch`로 승격했다.

## 적용 순서 제안

현재 상태를 다시 만들 때 권장 순서는 다음이다.

1. U-Boot workspace에 `0005-am64x-rm-cfg-share-icssg1-pktdma-with-main-0-r5-1.patch` 적용
2. U-Boot boot artifact 재빌드 후 SD boot media에 반영
3. 필요 시 Linux workspace에 `0003-arm64-dts-ti-k3-am642-evm-add-icssg1-r5f-owner-overlay.patch` 적용
4. TMDS64EVM에서 temporary `firmware-name` override 또는 정식 firmware 배치 경로 선택
5. Path B MCU+ workspace는 `0004-...integration-reference.patch`를 기준으로 clean replay patch를 별도 정리

대표 명령 예시는 다음과 같다.

```bash
git -C workspace/ti-u-boot-sdk12 apply \
  bsp/u-boot/patches/0005-am64x-rm-cfg-share-icssg1-pktdma-with-main-0-r5-1.patch

tools/build/build-u-boot.sh
tools/install/install-bootloader-to-sd.sh

git -C workspace/ti-linux-kernel-sdk12 apply \
  bsp/linux/patches/0003-arm64-dts-ti-k3-am642-evm-add-icssg1-r5f-owner-overlay.patch

tools/build/build-kernel.sh
tools/install/install-kernel-to-sd.sh
```

주의:

- Linux DT overlay patch는 현재 성공 경로의 필수 조건이 아니라, temporary `fdt set`를 정식 DT 자산으로 승격할 때 쓰는 보관 자산이다.
- MCU+ Path B integration reference는 clean `git apply` 용이 아니므로, workspace 비교 기준으로 사용해야 한다.

## 다음 검증 제안

1. 실제 두 포트 L2 forwarding 검증
2. 실제 gPTP peer 연동 및 sync drift 관찰
3. 반복 reboot 회귀 검증
4. `300b2400.mdio` Linux probe를 장기 경로에서 유지할지 비활성화할지 결정
5. `.icss_mem` / `.enet_dma_mem` donor parity 복원 필요성 검토
6. MCU+ Path B integration reference를 clean replay patch 세트로 재정리
