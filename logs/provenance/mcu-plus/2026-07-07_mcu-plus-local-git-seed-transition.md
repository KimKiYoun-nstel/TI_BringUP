# 2026-07-07 MCU+ local git seed transition

## 목적

기존 `workspace/mcu_plus_sdk_am64x_12_00_00_27` full-copy 기반 운영을 중단하고,

- external original은 reference-only로 유지하고
- local bare seed repo를 만들고
- repo `workspace/`에는 git-managed clone을 두는 구조

로 전환한 사실을 기록한다.

## 원본과 seed

- external original:
  - `~/ti/am64x/mcu_plus_sdk_am64x_12_00_00_27`
- local bare seed repo:
  - `~/ti/local_git_repo/mcu_plus_sdk_am64x_12_00_00_27.git`

원본 tree는 수정하지 않았고,
bare repo에 `--work-tree`로 original snapshot을 읽어 baseline commit을 만들었다.

## baseline

```text
branch : main
tag    : ti-mcu-plus-sdk-12.00.00.27-baseline
commit : 44bd053 baseline: import mcu plus sdk 12.00.00.27
```

## 새 workspace

- path:
  - `workspace/mcu_plus_sdk_am64x_12_00_00_27`
- origin:
  - `/home/nstel/ti/local_git_repo/mcu_plus_sdk_am64x_12_00_00_27.git`

## C Case 흡수 방식

기존 full-copy workspace에서 C Case 관련 의미 있는 변경만 새 git workspace branch로 다시 흡수했다.

branch:

```text
phase2-tsn-c-case
```

commit:

```text
6f7e325b tsn: add remoteproc gptp icssg project
723147ec tsn: trace remoteproc gptp bridge path
```

이 branch는 local seed repo에도 push했다.

## project patch export

위 두 commit은 project 내부 patch set으로도 export했다.

```text
projects/tsn_c_case/patches/0001-tsn-add-remoteproc-gptp-icssg-project.patch
projects/tsn_c_case/patches/0002-tsn-trace-remoteproc-gptp-bridge-path.patch
```

## 기존 full-copy workspace에서 버린 residue

다음은 새 canonical workspace 상태로 가져오지 않았다.

- object/output/build artifact
- `Debug/`, `Release/*.o`, `Release/syscfg/*.o`, `.clangd` cache
- `gptp_icssg_switch.release.*`, `*.out`, `*.map`, `*.mcelf*`
- temporary extra imported project residue
  - `hello_world_am64x-sk_a53ss0-0_nortos_gcc-aarch64`
  - `ipc_rpmsg_echo_linux_am64x-evm_r5fss0-0_freertos_ti-arm-clang`

이들은 canonical source replay 자산이 아니라 실험/빌드 residue로 판단했다.

## 기존 non-C-Case 변경 보존 상태

old workspace에 있던 기존 non-C-Case 의미 있는 변경은 이미 repo 자산으로 보존되어 있었다.

- `bsp/mcu-plus/patches/0002-am64x-sbl-ospi-linux-keep-lp4-dual-boot-workspace-base.patch`
- `bsp/mcu-plus/patches/0003-am64x-linuxappimagegen-pyelftools-compat.patch`
- `bsp/mcu-plus/syscfg/board_ddrReginit_sk_am64b_lpddr4.h`

즉 기존 full-copy tree를 유지해야만 재현되는 상태는 아니라고 판단했다.
