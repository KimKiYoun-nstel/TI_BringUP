# 2026-11-04 새 호스트 bring-up 준비 상태 검토

## 결론과 범위

**소스 분석과 bring-up 개발을 재개할 기본 환경은 갖춰져 있다. 다만 모든 이미지 생성·배포 경로가 즉시 준비된 상태는 아니다.**

- Ubuntu 24.04의 SDK 경로, 주요 컴파일러 실행, source baseline/patch, 이전 자산 무결성은 확인했다.
- 확정적인 실행 차단은 MCU+ MCELF 생성기의 Python `construct` 누락이다. Git 작성자 정보도 설정되지 않았다.
- 공용 workspace 검증기의 옛 홈 경로와 검사 범위는 보완해야 한다. 이번에는 현재 경로와 Git 상태를 별도로 검사했다.
- TFTP/NFS와 프로젝트별 local-fullchain 준비는 해당 작업을 재개할 때 완료한다.
- 전체 빌드, 이미지 생성, flash/deploy, 보드 접속·부팅은 실행하지 않았다. UART와 UART MCP는 검토에서 제외했다.
- 이번 변경은 검토 문서와 재구성 문서의 참조 링크다. 패키지 설치, Git 설정 변경, source/SDK 수정은 수행하지 않았다.

## 검토 기준과 증적

우선순위는 최종 재구성 기록 → 호스트 설치 기록 → 초기 이전 감사 기록 순서다.

- [대상 workspace 재구성](2026-11-04_target-workspace-reconstruction.md)
- [Ubuntu 24.04 호스트 이전](2026-11-04_ubuntu24-host-migration.md)
- [Git/workspace 이전 감사](2026-11-04_git-workspace-migration-audit.md)
- `PROJECT_BRIEF.md`, `README.md`, `AGENTS.md`, `sdk-manifest/{workspace-baseline.md,source-commits.md,workspaces.yml}`
- `~/ti/migration-logs/`: 설치·재설치·재구성 로그, `final-source-verification.txt`, `archive-verification.json`
- `~/ti/migration-archives/20261104/`: 설계/이미지 archive와 파일별 manifest

기존 문서의 WSL Ubuntu 22.04 및 `/home/nstel`은 과거 환경 기록이다. 새 호스트의 실제 실행 경로는 `tools/env/*.env`와 DTS의 `config/paths.local.yaml`을 기준으로 확인했다. MCU+ 재설치 baseline SHA와 TF-A/OP-TEE HEAD는 초기 manifest와 차이가 있지만 최종 재구성 기록과 일치한다.

## 확인된 정상 항목

### 호스트와 도구

| 항목 | 실측 결과 |
|---|---|
| OS/아키텍처 | Ubuntu 24.04.4 LTS, native Linux x86_64 |
| 자원 | 논리 CPU 12개, RAM 약 31GiB, swap 8GiB, 디스크 약 278GB 가용 |
| 네트워크 | `enp5s0`, `192.168.0.107/24`, 기본 gateway `192.168.0.1` |
| Linux SDK | `~/ti/am64x/ti-processor-sdk-linux-am64xx-evm-12.00.00.07.04` |
| MCU+ 설치/작업본 | `~/ti/am64x/mcu_plus_sdk_am64x_12_00_00_27` / repo의 `workspace/mcu_plus_sdk_am64x_12_00_00_27` |
| CCS | `~/ti/ccs2040/ccs` 및 headless CLI 파일 존재 |
| A53/R5 cross compiler | SDK GCC 15.2.0; compiler frontend, assembler, linker 실행 성공 |
| MCU+ compiler | TI Arm Clang 4.0.4.LTS, A53 bare-metal GCC 9.2.1 실행 성공 |
| SysConfig | CCS 내 CLI `1.26.0+4407` 실행 성공 |
| Python | 3.12.3; PyYAML, pyelftools 0.30, setuptools, cryptography 41.0.7 import 성공 |

`build-essential`, `bc`, `bison`, `flex`, `libssl-dev`, `libelf-dev`, `libncurses-dev`, `swig`, `device-tree-compiler`, `cpio`, `gawk`, `rsync`, `cmake`, `ninja-build`, `pkg-config`, `git-lfs`, Python 개발/venv 패키지 등 주요 호스트 의존성은 설치되어 있다.

`check-env.sh`, `check-mcu-plus-env.sh`, `verify-workspace-state.sh`는 모두 통과했다. 마지막 검사의 한계는 아래에 별도로 기록한다. SDK의 bootloader prebuilts, filesystem 디렉터리, OP-TEE helper가 사용하는 TA32 sysroot도 존재한다.

SDK A53 GCC를 환경 정리 없이 호출한 `-print-libgcc-file-name`은 `libgcc.a`만 반환했다. 실제 devkit의 `libgcc.a`는 존재하고, `build-u-boot.sh`는 별도 검색·지정 로직을 갖고 있다. 이 출력만으로 설치 실패라고 판정하지 않으며, 직접 `make`를 호출할 때는 repo helper의 환경 정리와 sysroot/libgcc 처리를 따라야 한다.

### 소스와 patch

6개 작업본 모두 staged/unstaged/untracked 변경이 없다.

| workspace | branch | HEAD |
|---|---|---|
| `ti-linux-kernel-sdk12` | `migration-reconstructed` | `c214492085504176b9c252a7175e4e60b4b442af` |
| `ti-u-boot-sdk12` | `migration-reconstructed` | `3b922aef185897b244ae1d03fe9053fe99f1948b` |
| `ti-u-boot-sdk12-sk-am64b-local-fullchain` | `migration-local-fullchain` | `aa2cfc68ec252fa75ccb45fe8b15f8b52ed65877` |
| `mcu_plus_sdk_am64x_12_00_00_27` | `phase2-tsn-c-case` | `af8d69d3b7e66ae5130770f234a9559dce9a366f` |
| `trusted-firmware-a-2.14+git` | `migration-reconstructed` | `44fcd9c2d62460a780a5e76f6e65202c37d8dbb7` |
| `optee-os-4.9.0+git` | `migration-reconstructed` | `60706ecef7619a01c5f5da20ea12a832699a1440` |

- U-Boot baseline `2549829cc194ffd9e38b755d2e10c7fc4cd971eb`와 Linux baseline tag를 확인했다.
- U-Boot RM `0001`, bootdelay `0002`/`0006`, MCU+ C Case `0001`/`0002`의 stable patch-id를 현재 commit과 다시 비교해 모두 일치했다.
- U-Boot linked worktree 경로는 새 홈 경로다. MCU+ local bare seed에 `main`(`f370eb54efe59104b2335ad6c799a979543239a1`)과 C Case branch가 존재한다.
- 상위 repo의 `git ls-remote origin refs/heads/main`은 성공했고 검토 시작 HEAD `199b5ac30a2676cb4c6b8ea52fa5ddec7481d8cd`와 같았다. 이는 원격 읽기 성공이며 push 권한 확인은 아니다.

### 이전 자산

파일별 manifest로 **현재 repo 내 복원 파일의 size/SHA-256을 전수 재검사**했다.

| 자산 | 파일 수 | 합계 bytes | 결과 |
|---|---:|---:|---|
| board-design | 99 | 6,757,180 | 누락/불일치 없음 |
| board-images | 5,832 | 1,726,644,559 | 누락/불일치 없음 |

설계 자산에는 netlist, hardware_db, PDF, SysConfig DB, 생성/전달 DTS와 root-managed Linux/U-Boot DTS set이 포함된다. DTS local 설정에 대해 기존 `load_config()`/`validate_config()`만 호출하여 새 경로, 입력 파일, reference DTS, DB 필수 열 검사를 통과했다. DTS 생성은 실행하지 않았다. 여기서 `.NET`은 회로 netlist 확장자이며 .NET SDK 의존성을 뜻하지 않는다.

이전된 `out/`과 TFTP payload는 보존 자산이다. 새 호스트에서 재빌드·실부팅 성공한 증거로 취급하지 않는다. TSN raw artifacts/log 및 `.agents/` 미이전은 확정된 이전 범위이며 누락 장애로 분류하지 않는다.

## 보완 항목과 영향

### 1. MCU+ MCELF 생성: 확정 차단

재현 명령:

```bash
python3 -B workspace/mcu_plus_sdk_am64x_12_00_00_27/tools/boot/multicore-elf/genimage_am64x.py --help
```

결과는 `modules/elf_structs.py` import 중 `ModuleNotFoundError: No module named 'construct'`다. 실제 빌드 없이 재현했다.

- 영향: `gen-r5f-multicore-appimage.sh --execute`, MCELF 형식 `linuxAppimageGen` 및 이를 사용하는 SBL local-fullchain 이미지 조립.
- 보완: 해당 작업 전에 프로젝트 Python 환경에서 `construct`를 준비하고 동일 `--help`부터 재확인한다. SDK requirements에는 `construct==2.10.70`이 명시되어 있다.
- requirements의 `cryptography==2.8` 등 과거 고정 버전을 Python 3.12 system 환경에 일괄 덮어쓰는 방식은 피하고, 실제 사용하는 경로에 맞춰 호환성을 확인한다.
- `Cryptodome`도 현재 import 불가다. U-Boot binman `pre_load`와 OP-TEE `sign_rproc_fw.py` 등 해당 기능을 사용할 때 보완한다. 일반 AM64x 이미지 경로 전체가 이 모듈 때문에 실패한다고 단정하지 않는다.
- pyelftools는 설치되어 있으나 MCU+ SBL용 `0003` 호환 patch 적용은 별도 준비 사항이다.

### 2. Git 작성자: commit/patch 개발 전에 설정 필요

상위 repo에서 `git var GIT_AUTHOR_IDENT`는 `Author identity unknown`으로 실패했다. `user.name`/`user.email`도 조회되지 않았다. clone/fetch 또는 기존 소스 분석에는 영향이 없지만 새 commit과 `git am` 기반 재구성 등에 앞서 사용자의 실제 identity 설정이 필요하다. 이번 검토에서 임의 값을 설정하지 않았다.

### 3. 공용 검증기: 통과 결과의 사각지대

`tools/prepare/verify-workspace-state.sh`에는 MCU+ 원본의 두 `sciclient_defaultBoardcfg_rm*.c` 경로가 `/home/nstel/ti/...`로 남아 있어 새 호스트에서는 해당 검사를 건너뛴다. Git 검사도 `git diff --quiet`이므로 staged/untracked는 검사하지 않는다.

이번에는 현재 MCU+ **설치 원본** 경로의 두 파일에 대해 동일한 금지 GPIOMUX 패턴이 없는지 별도 검사했고, 6개 workspace는 `git status --short --untracked-files=all`로 보완했다. 현재 오염 증거는 없지만 장기적으로 검증기의 경로와 검사 범위를 수정해야 한다. 최종 재구성 문서에서 공용 검증기 수정은 제외했으므로 이번에도 문제와 보완 방법을 기록했다.

### 4. SBL local-fullchain: 목적별 준비 후 재개

- 현재 MCU+ 작업본은 C Case다. `apply-mcu-plus-sk-am64b-sbl-ospi-linux-local-fullchain.sh --check`는 DDR LPDDR4 자산 불일치로 실패했다. 이는 SBL patch가 적용되지 않은 현재 목적 선택과 부합한다.
- C Case branch에 SBL patch를 무조건 누적하지 않고, 별도 topic에서 LPDDR4 및 pyelftools 호환 patch 등 해당 프로젝트의 준비 절차를 따른다.
- `bootstrap-sk-am64b-sbl-ospi-linux-local-fullchain.sh --print`의 새 경로는 정상이다.
- `gen-linux-appimage-for-sbl.sh --print --profile local-fullchain`은 workspace의 TF-A `build/k3/lite/release/bl31.bin`과 OP-TEE `out/arm-plat-k3/core/tee-pager_v2.bin` 부재로 SHA 계산에 실패했다. 이전 archive는 해당 workspace 빌드 출력을 보장하지 않는다.
- 따라서 기존 U-Boot 출력 파일이 있더라도 전체 local-fullchain 입력 준비 완료로 보지 않는다. 해당 작업에서 source bootstrap과 위 Python 의존성을 함께 확인한다.

### 5. 네트워크 배포·추가 도구: 사용하는 작업에서 준비

- `tftpd-hpa`/`nfs-kernel-server` 서비스는 `LoadState=not-found`다. payload 복원과 서비스 운영은 별개이므로 TFTP/PXE/NFS 작업 전에 설치·root/export·방화벽·보드 `serverip`를 새 호스트 기준으로 확인한다.
- install helper에는 기존 실험 보드 IP 기본값이 남아 있다. 실제 대상 IP, SSH 인증, 배포 목적지는 해당 작업에서 확인한다. 이번에는 보드에 접속하지 않았다.
- 호스트 `mkimage`/`u-boot-tools`는 없다. U-Boot 자체 빌드가 만드는 도구와 구분하며, 호스트 `mkimage` 직접 호출이 필요한 작업에서 설치 여부를 판단한다.
- 선택 도구인 `gcc-arm-none-eabi-9-2019-q4-major`와 `ti-cgt-pru_2.3.3`은 없다. 현재 확인한 TI Clang R5/A53 경로의 공통 차단은 아니며 ARM GCC/PRU 대상 작업에서 준비한다.
- CCS GUI, headless 프로젝트 import/build, JTAG/debug probe 실동작은 미확인이다. CLI 파일 존재나 SysConfig 버전 출력으로 이 단계까지 검증되었다고 보지 않는다.

## 다음 실제 작업에서의 적용 순서

1. 새 개발 commit이 필요하면 Git identity를 설정하고 해당 workspace topic branch를 선택한다.
2. `check-env.sh`, `check-mcu-plus-env.sh`, `verify-workspace-state.sh`와 전체 Git 상태를 확인한다. 검증기 수정 전에는 MCU+ 원본의 현재 경로 검사도 병행한다.
3. 대상이 MCELF/SBL이면 `construct` 및 목적별 MCU+ patch와 TF-A/OP-TEE 입력을 먼저 준비한다.
4. 해당 프로젝트의 최소 필요 target부터 빌드하여 Ubuntu 24.04/Python 3.12/GCC 호환성을 확인하고, 실패 시 명령·첫 오류·로그를 기록한다.
5. 배포가 필요해지는 시점에 SSH/TFTP/NFS 또는 debug probe를 검증한다.

`tools/{build,prepare,install}/*.sh`의 Bash 구문 검사도 통과했다. 이는 실행 경로와 실제 빌드 성공을 대신하지 않는다.
