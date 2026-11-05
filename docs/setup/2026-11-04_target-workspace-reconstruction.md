# 대상 호스트 workspace 재구성 및 동기화 가이드

## 적용 기준

- 대상: Ubuntu 24.04.4, `prodigyrcn@192.168.0.107`, `~/ti/TI_Bringup`.
- CCS/SDK/toolchain은 **원본 installer 또는 배포 압축파일을 전송한 뒤 대상에서 설치/해제**한다. 원본 장비의 설치 폴더나 workspace checkout을 전송하지 않는다.
- 상위 Git은 UART 관련 파일의 미커밋 변경을 제외하고 작업별 commit/push한다.
- TSN raw artifacts/log와 `.agents/`는 전송하지 않는다. 원본 자료 삭제는 하지 않는다.
- 회로도 PDF, hardware/SysConfig DB, DTS 자산과 보드 image는 동기화한다. 다수 파일은 archive로 전송 후 대상에서 해제한다.

## 1. 이미 설치한 원본 패키지

| 패키지 | 대상 설치 경로 |
|---|---|
| `CCS_20.4.0.00013_linux.zip` | `~/ti/ccs2040`, 내장 SysConfig 1.26.0 및 TI Arm Clang 4.0.4 |
| `ti-processor-sdk-linux-am64xx-evm-12.00.00.07.04-Linux-x86-Install.bin` | `~/ti/am64x/ti-processor-sdk-linux-am64xx-evm-12.00.00.07.04` |
| `mcu_plus_sdk_am64x_12_00_00_27-linux-x64-installer.run` | `~/ti/am64x/mcu_plus_sdk_am64x_12_00_00_27` |
| `gcc-arm-9.2-2019.12-x86_64-aarch64-none-elf.tar.xz` | `~/ti/gcc-arm-9.2-2019.12-x86_64-aarch64-none-elf` |

원본 파일과 설치 방법 및 SHA-256은 [설치 기록](2026-11-04_ubuntu24-host-migration.md)에 있다. MCU+ SDK는 standalone SDK이며 Linux SDK 설치만으로 생성되지 않는다. TF-A/OP-TEE source는 Linux SDK 안에 있으나 현재 프로젝트가 사용하는 정확한 commit은 추가 Git fetch가 필요하다.

MCU+ installer의 `--prefix`는 SDK 자체 경로가 아니라 부모 `"$HOME/ti/am64x"`로
지정해야 한다. 설치 후 `~/ti/am64x/mcu_plus_sdk_am64x_12_00_00_27/imports.mak`가
직접 존재해야 하며 재구성 도구가 이를 사전 검사한다.

## 2. README의 로컬 가이드 참조 정리

감사 당시 README 3개가 아래 작업 계획 4개를 직접 참조했다.

| README | 과거 참조한 `.agents/` 파일 | 현재 기준 |
|---|---|---|
| `projects/am64x-tsn-quant-validation/README.md` | `AM64x_TSN_정량_검증_가이드.md`, `AM64x_TSN_정량_검증_TI_SDK_활용_추가_가이드.md` | 프로젝트 `docs/measurement-plan.md`, P1/P2/P3 계획·결과 |
| `projects/tsn_dscp_pcp/README.md` | `am64x_sk_tsn_switch_tmds_endpoint_env_setup.md` | `docs/plan.md`, `board-matrix.md`, Test B replay guide |
| `projects/tsn_c_case/README.md` | `am64x_c_case_execution_roadmap_plan.md` | `docs/project-review.md`, `closure-status.md` |

작업 시작 때 사용한 로컬 계획을 README가 기준 문서로 남겨 둔 상태였다. 소스/빌드 의존성이 아니므로 README를 repo-managed 문서 기준으로 정리했다. 과거 문서에 남은 가이드 이름은 이력 설명이며 해당 파일의 대상 전송을 요구하지 않는다.

## 3. source 재구성

실행 도구: `tools/prepare/reconstruct-host-workspaces.sh`.

```bash
cd ~/ti/TI_Bringup
# .env가 없을 때만 각 템플릿에서 생성한다.
cp tools/env/sdk-12.00.00.07.04.env.example tools/env/sdk-12.00.00.07.04.env
cp tools/env/mcu-plus-sdk-am64x-12.00.00.env.example tools/env/mcu-plus-sdk-am64x-12.00.00.env
bash tools/prepare/reconstruct-host-workspaces.sh --execute
```

이 도구는 기존 목적지 source/seed가 있으면 덮어쓰지 않고 중단한다. 이번 대상의 초기 U-Boot/Linux 폴더는 `create-workspace.sh`가 설치 직후 복사한 것이므로 상태 확인 후 대상의 `~/ti/migration-logs/initial-source-copies-20261104/`로 보관하고 재구성한다. 원본 장비의 workspace는 건드리지 않는다.

| 재구성 source | 입력과 선택 delta |
|---|---|
| Linux | 대상 설치 SDK source에서 Git clone, `c214492085504176b9c252a7175e4e60b4b442af`, clean topic 및 baseline tag |
| 기본 U-Boot | 대상 설치 SDK source에서 Git clone, `2549829cc194ffd9e38b755d2e10c7fc4cd971eb` + 공식 `0002` bootdelay=5 |
| U-Boot local-fullchain | 같은 Git repo의 새 linked worktree, baseline + RM `0001` + 선택 전용 `0006` bootdelay=10 |
| TF-A | 대상 설치 SDK Git에서 clone 후 필요하면 upstream fetch, `44fcd9c2d62460a780a5e76f6e65202c37d8dbb7` |
| OP-TEE | 대상 설치 SDK Git에서 clone 후 필요하면 upstream fetch, `60706ecef7619a01c5f5da20ea12a832699a1440` |
| MCU+ C Case | 대상에서 설치한 MCU+ source를 **대상 내부에서** workspace에 복사, Git baseline 초기화 후 `projects/tsn_c_case/patches/0001`, `0002` 적용 |
| MCU+ local seed | 위 재구성 Git repo로부터 대상 내부에 bare clone 생성 |

`0006`은 원본 local-fullchain commit의 stable patch-id와 대조한 선택 자산이다. 기본 `series`에는 추가하지 않는다. bootdelay=5/10을 같은 topic에 누적 적용하지 않는다.

MCU+ baseline과 patch 적용 commit SHA는 import 시각/committer 차이로 원본과 달라질 수 있다. source delta는 공식 patch와 patch-id로 확인한다. SBL 목적의 MCU+ 변경은 `bsp/mcu-plus/patches/series` 및 해당 prepare helper를 별도 topic에서 선택하며 C Case에 일괄 누적하지 않는다.

TF-A/OP-TEE의 과거 진단용 `*-diag` working diff/stash는 이번 재구성에 자동 적용하지 않는다. 현재 canonical source와 과거 diagnostic image를 구분한다. 원본 설치 SDK는 수정하지 않는다. Git identity는 해당 실행 프로세스에서만 지정하며 사용자 전역 Git 설정은 변경하지 않는다.

## 4. 회로도/DB 및 image archive

대상 archive 위치: `~/ti/migration-archives/20261104/`.

| archive | 원본 파일 수 / 크기 | 압축 크기 | 내용 |
|---|---:|---:|---|
| `board-design.tar.gz` | 99 / 6,757,180 bytes | 2,836,161 bytes | PDF, hardware_db, SysConfig DB, netlist, reference/generated/delivery DTS, root-managed DTS sets |
| `board-images.tar.gz` | 5,832 / 1,726,644,559 bytes | 548,444,500 bytes | `out/`의 배포 가능 Image/DTB/modules/bootloader/firmware/initramfs, 설정·manifest, TFTP golden/canonical payload |

설치된 SDK/source checkout, object/archive cache, TSN raw capture/log, `.agents/`는 archive에 포함하지 않는다. image archive의 diagnostic binary는 과거 실험 산출물이며 새 canonical 이미지로 승격한 것이 아니다. 별도 `.wic*` 파일은 원본 `~/ti`에서 발견되지 않았다. SDK 제공 rootfs tar는 대상에서 재설치된 SDK의 `filesystem/`에 있다.

각 archive와 함께 다음을 전달한다.

- `SHA256SUMS`: archive와 manifest 자체의 SHA-256
- `board-design.manifest.json`, `board-images.manifest.json`: 상대 경로, size, 파일별 SHA-256

대상에서 archive SHA-256을 확인한 후 `~/ti/TI_Bringup` 기준으로 해제하고, manifest의 **모든 파일**을 다시 대조한다. DB의 Git 추적본은 Git pull로도 도착하지만 PDF/관련 자산과 같은 snapshot인지 함께 확인한다.

## 5. 새 사용자 경로 대응 및 확인

- DTS local 설정은 `tools/custom_board_dts_workflow/config/paths.local.yaml.example`에서 만들고 세 절대 경로(`project_root`, `linux_dts_dir`, `linux_include_dir`)를 `/home/prodigyrcn/...`로 지정한다.
- `tools/prepare/verify-workspace-state.sh`는 U-Boot/Linux source의 clean 여부를 확인한다. 내부 MCU+ 외부 변경 검사는 `/home/nstel/...` 하드코딩이 있으므로, 새 대상에서는 실제 설치 경로를 별도 확인해야 한다. 이 공용 검증 스크립트 자체는 이번에 수정하지 않는다.
- UART 관련 미커밋 6개 파일은 원본에 남겨 두며 새 장비에 동기화하지 않는다. 대상 UART endpoint/tool은 별도 업데이트 작업이다.
- `.agents/`, TSN artifacts/log가 없더라도 README의 현재 기준과 P3 결과 문서를 읽고 작업을 이어갈 수 있다. 기존 raw 재집계는 별도 요청 전까지 대상에서 수행하지 않는다.
- `out/` 및 TFTP의 이전 binary는 SHA-256까지 확인하되 Ubuntu 24.04에서 새로 빌드/boot한 결과로 표현하지 않는다. 전체 build/실보드 boot는 별도 검증 단계다.

## 실행 결과

2026-11-04 대상에서 실행 및 검증을 완료했다.

| source | 대상 HEAD |
|---|---|
| 기본 U-Boot | `3b922aef185897b244ae1d03fe9053fe99f1948b` |
| local-fullchain U-Boot | `aa2cfc68ec252fa75ccb45fe8b15f8b52ed65877` |
| Linux | `c214492085504176b9c252a7175e4e60b4b442af` |
| MCU+ C Case | `af8d69d3b7e66ae5130770f234a9559dce9a366f` |
| MCU+ 재설치 baseline | `f370eb54efe59104b2335ad6c799a979543239a1` |
| TF-A | `44fcd9c2d62460a780a5e76f6e65202c37d8dbb7` |
| OP-TEE | `60706ecef7619a01c5f5da20ea12a832699a1440` |

- 6개 source의 tracked/untracked 변경 없음 확인, `verify-workspace-state.sh` 통과.
- U-Boot bootdelay=5/10과 MCU+ C Case 두 commit의 stable patch-id가 각각 공식 patch와 일치.
- MCU+ local bare seed에 `main`과 `phase2-tsn-c-case` 생성 완료.
- 최초 MCU+ 재구성은 중첩 prefix 때문에 두 번째 patch에서 실패했다. 기존 설치와 실패 사본은 대상 migration log 영역에 보관했다. 원본 installer를 올바른 prefix로 재실행하고 `--execute-mcu`로 MCU+ 단계만 재구성하여 성공했다. 이 옵션도 기존 목적지가 없어야 실행된다.
- 원본 C Case patch에는 생성 makefile의 whitespace 경고가 있으나 내용 변경 없이 두 patch 모두 적용 성공했다.
- archive 및 manifest 자체의 SHA-256, 해제 후 99 + 5,832개 파일의 size/SHA-256 전수 일치.
- 대상 DTS local 경로 3개를 새 홈 경로로 생성했다. 상위 repo는 clean이며 공용 UART 파일은 이전 시작 커밋과 동일하다.
- 대상 `.agents/` 부재 및 quantitative-validation `artifacts/`에 `.gitkeep`만 있는 상태 확인.
- 전체 kernel/U-Boot/MCU+ build나 보드 boot는 실행하지 않았다. 현재 확인은 source 재구성, patch 동일성 및 이전 binary 무결성 범위다.
- 작업 후 대상 가용 디스크 약 278GB.

압축파일 SHA-256:

```text
c23bacd3e7c0eff7f5e8c2839dae78deff3e177ca3ab646a5cf91942a666bda9  board-design.tar.gz
c05d03076bb86d6c4cc095f97e28781c387dc11e742246e7a987f37a0652e3ba  board-images.tar.gz
```

대상 증적 경로:

- `~/ti/migration-archives/20261104/`: archive 2개, 파일별 manifest 2개, `SHA256SUMS`.
- `~/ti/migration-logs/archive-verification.json`: 99개/5,832개 파일 전수 검증 결과.
- `~/ti/migration-logs/workspace-reconstruction.log`: 최초 source 재구성과 MCU+ 실패 원인.
- `~/ti/migration-logs/mcu-plus-reinstall.log`, `workspace-reconstruction-mcu.log`: 재설치 및 MCU+ 재구성 성공.
- `~/ti/migration-logs/final-source-verification.txt`: source SHA, patch-id, clean 상태, UART 제외 확인.
- `~/ti/migration-logs/initial-source-copies-20261104/`, `mcu-plus-prefix-initial-20261104/`, `mcu-plus-first-reconstruction-20261104/`: 대상에서 생성했던 초기/실패 사본 보관. 원본 장비에서 설치 폴더를 전송한 것이 아니다.

## 후속 호스트 준비 상태 검토

재구성 이후의 비빌드 실행 점검과 보완 항목은 [새 호스트 bring-up 준비 상태 검토](2026-11-04_host-bringup-readiness-review.md)에 정리했다. MCU+ `construct` 누락, Git identity, 공용 검증기의 옛 경로, 프로젝트별 SBL 입력 및 네트워크 배포 준비를 구분한다. UART/MCP와 실제 빌드·부팅은 해당 검토 범위에서도 제외했다.
