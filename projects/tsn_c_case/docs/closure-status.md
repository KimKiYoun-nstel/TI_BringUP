# AM64x TSN C Case Closure Status

## 목적

`projects/tsn_c_case`를 현재 시점에서 마감하려 할 때,

1. 최종 기술 결론이 무엇인지
2. project 내부 파일 정리가 어디까지 끝났는지
3. `workspace/`에 어떤 C Case residue가 남아 있는지
4. 실제 boot image와 firmware에 어떤 연관성이 남아 있는지

를 한 번에 판단할 수 있도록 정리한다.

## 최종 결론

- `gptp_icssg_switch` donor 기반 Path B Linux remoteproc bring-up은 성공했다.
- 그러나 donor와 같은 bridge-generated gPTP 기능은 성립하지 않았다.
- 현재 direct blocker는 `asCapableAcrossDomains` 미성립이다.
- 따라서 현재 이식 상태는 donor와 **behaviorally equivalent 하지 않다.**

판단 근거의 기준 문서는 다음 두 개다.

- `2026-07-06_gptp-bridge-fresh-start-validation.md`
- `resource-ownership-audit.md`

## project 내부 정리 상태

### 정리된 것

- 단계별 진행 문서는 `docs/archive/`로 이동했다.
- 중복 raw log는 정리하고 `logs/reference/`에 최소 reference log만 남겼다.
- 최종 non-equivalent 결론은 `2026-07-06_gptp-bridge-fresh-start-validation.md`에 고정했다.

### 아직 남아 있던 혼선

이번 정리 전에는 다음 혼선이 있었다.

- `README.md`와 `docs/phase1-summary.md`가 아직 bring-up 성공 중심 서술로 남아 있었다.
- 즉 `remoteproc bring-up 성공`과 `donor-equivalent 기능 성공`이 분리되어 보이지 않았다.

현재 기준은 다음처럼 본다.

- `phase1-summary.md`
  - Path B bring-up 성공 범위를 설명하는 중간 단계 문서
- `2026-07-06_gptp-bridge-fresh-start-validation.md`
  - donor-equivalent 기능 여부의 최종 판정 문서
- 이 문서
  - project closure, residue, boot image 연관성까지 묶어 보는 마감 문서

### 아직 residue로 남긴 것

- `tmp_guide/c6_icssg_firmware_switch_basic_validation_guide.md`
  - 현재도 임시 가이드 성격이 강하다.
  - 최종 canonical 문서로 승격하지 않았다.

즉 project 내부 문서는 이제 방향은 정리됐지만,
`tmp_guide/` 같은 임시 자산은 아직 완전 삭제/승격 판단이 끝난 상태는 아니다.

## workspace residue 상태

## U-Boot workspace

정리 전 dirty file:

- `workspace/ti-u-boot-sdk12/board/ti/am64x/rm-cfg.yaml`

의미:

- `ICSSG_1 PKTDMA` resource를 `A53_2 (12)`와 `MAIN_0_R5_1 (36)`가 함께 쓰도록 한 C Case 핵심 변경이다.

repo 승격 상태:

- patch: `bsp/u-boot/patches/0005-am64x-rm-cfg-share-icssg1-pktdma-with-main-0-r5-1.patch`
- provenance: `logs/provenance/u-boot/2026-07-02_tmds64evm_tsn-c-case_rm-cfg-main-r5-1.md`

판정:

- repo-managed patch/provenance export를 확인한 뒤 workspace를 clean reset했다.
- 현재 `workspace/ti-u-boot-sdk12`는 unstaged diff가 없다.

## Linux workspace

정리 전 dirty files:

- `workspace/ti-linux-kernel-sdk12/arch/arm64/boot/dts/ti/Makefile`
- `workspace/ti-linux-kernel-sdk12/arch/arm64/boot/dts/ti/k3-am642-evm-icssg1-r5f-owner.dtso`

의미:

- Linux ICSSG1 Ethernet ownership을 끄고 R5F firmware path를 돕는 overlay 보관 자산이다.

repo 승격 상태:

- patch: `bsp/linux/patches/0003-arm64-dts-ti-k3-am642-evm-add-icssg1-r5f-owner-overlay.patch`
- provenance: `logs/provenance/linux/2026-07-02_tmds64evm_tsn-c-case_icssg1-r5f-owner-overlay.md`

판정:

- repo-managed patch/provenance export를 확인한 뒤 workspace를 clean reset했다.
- 현재 `workspace/ti-linux-kernel-sdk12`는 unstaged diff가 없다.
- 다만 이 overlay는 최종 성공 경로의 필수 boot artifact라기보다, temporary `fdt set`를 정식 DT 자산으로 보관한 성격이 강하다.

## MCU+ workspace

상태 특징:

- `workspace/mcu_plus_sdk_am64x_12_00_00_27`는 이제 local bare seed repo에서 clone한 git workspace다.
- local seed repo:
  - `~/ti/local_git_repo/mcu_plus_sdk_am64x_12_00_00_27.git`
- baseline:
  - branch: `main`
  - tag: `ti-mcu-plus-sdk-12.00.00.27-baseline`
  - commit: `44bd053`
- 현재 C Case branch:
  - `phase2-tsn-c-case`

현재 C Case와 직접 연결된 residue:

- custom CCS project:
  - `ccs_projects/gptp_icssg_linux_remoteproc_am64x-evm_r5fss0-0_freertos_ti-arm-clang/`
- source-level trace/adaptation 변경:
  - `source/networking/tsn/tsn-stack/tsn_gptp/gptpman.c`
  - `source/networking/tsn/tsn-stack/tsn_gptp/md_pdelay_req_sm.c`
  - `source/networking/tsn/tsn-stack/tsn_gptp/md_sync_send_sm.c`
  - `source/networking/tsn/tsn-stack/tsn_gptp/port_sync_sync_send_sm.c`
  - `source/networking/tsn/tsn-stack/tsn_gptp/site_sync_sync_sm.c`
  - `source/networking/tsn/tsn-stack/tsn_gptp/tilld/lld_gptpnet.c`

또한 project 내부에 다음 residue가 있다.

- `rproc_trace_status.h`
- `linker.remoteproc.cmd`
- `ti_power_clock_config.remoteproc.c`
- `Release/subdir_rules.mk`의 local hook

repo 승격 상태:

- project patch set:
  - `projects/tsn_c_case/patches/0001-tsn-add-remoteproc-gptp-icssg-project.patch`
  - `projects/tsn_c_case/patches/0002-tsn-trace-remoteproc-gptp-bridge-path.patch`
- workspace branch copy:
  - local seed repo `phase2-tsn-c-case`
- historical reference diff:
  - `bsp/mcu-plus/patches/0004-am64x-gptp-icssg-linux-remoteproc-pathb-integration-reference.patch`
- provenance: `logs/provenance/mcu-plus/2026-07-02_tmds64evm_tsn-c-case_pathb_remoteproc.md`
- provenance: `logs/provenance/mcu-plus/2026-07-07_mcu-plus-local-git-seed-transition.md`

판정:

- full-copy 기반 residue는 제거 가능 상태까지 정리됐다.
- 이제 MCU+는
  - clean baseline branch
  - local seed repo
  - project patch set
  - project branch
  로 관리할 수 있다.
- 다만 C Case patch set의 장기 replay 검증은 아직 별도 build/reboot로 다시 확인하지 않았다.
- 현재 `tools/build/check-mcu-plus-env.sh` 기준 workspace/env는 정상이다.

## boot image / firmware 연관성

## 직접 연관이 남는 boot image

다음 세 bootloader artifact는 C Case와 직접 연결된다.

- `tiboot3.bin`
- `tispl.bin`
- `u-boot.img`

이유:

- U-Boot workspace의 `rm-cfg.yaml` 변경이 boot-chain resource assignment에 영향을 준다.
- provenance 기준으로 위 세 artifact가 재빌드되어 SD boot media에 반영됐다.

즉 현재 어떤 SD boot media에 이 세 파일이 올라가 있느냐에 따라,
그 boot chain은 여전히 C Case RM ownership 정책의 영향을 받을 수 있다.

2026-07-07 cleanup 결과:

- TMDS의 active boot partition file hash는 C Case host artifact와 일치했었다.
- 이후 active boot files를 아래 backup set으로 복원했다.
  - `/run/media/boot-mmcblk1p1/backup/bootloader/20260702_134807/`
- 복원 후 active hash:
  - `tiboot3.bin`: `323e4e949138d6ec167319bc0292b91cc964e63fe854957727611179c6589f6c`
  - `tispl.bin`: `3bc0c14f354d53d803d2871999e95b194c1ac5a88c3592cfaf9fd84f57202c25`
  - `u-boot.img`: `eb1498a093a62f9450da4d6ab841106112b690c5248516a4b81c504c9f80e6dd`
- 복원 전 active set은 안전을 위해 아래에 재백업했다.
  - `/run/media/boot-mmcblk1p1/backup/bootloader/20260707_cleanup_pre_restore/`

## 조건부 연관 자산

- `k3-am642-evm-icssg1-r5f-owner.dtbo`

의미:

- Linux workspace에는 overlay 자산이 남아 있지만,
- 실제 성공 검증은 이 DTBO를 영구 설치하지 않고 U-Boot temporary `fdt set`로 진행했다.

따라서 이 자산은 다음으로 분류한다.

- boot image에 반드시 남아 있는 현재 active artifact: 아님
- 필요 시 persistent DT path로 옮길 수 있는 보관 자산: 맞음

## runtime test firmware 연관성

- test firmware 이름: `gptp_icssg_linux_remoteproc_r5f0_0_test.out`

역할:

- TMDS에서 U-Boot temporary `firmware-name` override로만 올려 쓴 검증용 firmware였다.

현재 상태:

- board 쪽 test firmware 파일은 제거했다.
- 현재 board default firmware는 다시 `am64-main-r5f0_0-fw`다.
- 2026-07-07 restored bootloader로 reboot 후에도 `78000000.r5f`는
  `firmware=am64-main-r5f0_0-fw`, `state=running`으로 확인했다.

하지만 residue는 남아 있다.

- MCU+ workspace source/project 자체는 그대로 남아 있다.
- 즉 **board runtime은 default로 복귀했지만, source/workspace 관점에서는 C Case firmware lineage가 그대로 남아 있다.**

## board runtime cleanup 결과

### TMDS64EVM

- test firmware file 제거 유지
- active bootloader 3종을 backup set으로 복원
- reboot 후 `login:`까지 정상 복귀 확인
- reboot 후 `78000000.r5f`는 default firmware로 running 확인

### SK-AM64B

- `n0`, `n1` netns 제거
- `eth0`, `eth1`를 root namespace로 복귀
- `/tmp/gm.conf`, `/tmp/slv.conf` 삭제
- 현재 `eth0`, `eth1`는 root namespace에서 `UP,LOWER_UP` 상태다

## 현재 closure 판정

다음처럼 정리한다.

```text
project 문서 구조 정리: 부분 완료
project 최종 결론 고정: 완료
repo patch/provenance export: 완료
U-Boot workspace cleanup: 완료
Linux workspace cleanup: 완료
MCU+ workspace cleanup/replay 정리: 완료
boot image residue 판독: 완료
on-board residue 점검: 완료
```

즉 **프로젝트는 기술 결론, workspace closure, on-board cleanup까지 모두 닫혔다.**

## 마감 관점의 다음 액션

다음 액션은 cleanup 자체보다 기록/커밋 정리와 후속 일반 작업 전환이다.

1. U-Boot/Linux dirty workspace를 각각
   - 정리 완료
2. MCU+ workspace를 local seed repo + git-managed clone 구조로 전환한다.
   - 정리 완료
3. 실제 boot media에 남아 있는 `tiboot3.bin`/`tispl.bin`/`u-boot.img` lineage를 보드별로 재확인한다.
   - TMDS active boot partition 기준 정리 완료
4. board runtime에서 default firmware/temporary override residue가 남아 있는지 재점검한다.
   - TMDS/SK 기준 정리 완료

현재 문서 기준으로는 1-4가 모두 완료됐다.
