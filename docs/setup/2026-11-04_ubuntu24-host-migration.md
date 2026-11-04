# Ubuntu 24.04 개발 호스트 이전 준비 기록

> 이 문서는 최초 설치 준비 기록이다. 후속 사용자 확정 범위에 따른 Git 동기화,
> PDF/DB/image 전송 및 clean workspace 재구성은 완료했으며 최신 결과는
> [대상 workspace 재구성 가이드](2026-11-04_target-workspace-reconstruction.md)의 실행 결과를 따른다.

## 목적과 현재 결론

기존 `~/ti` 경로 구조를 새 장비에서 재구성한다. CCS/SDK의 설치된 폴더를 복사하는 대신 **원본 설치 패키지를 전송하고 새 홈 경로에 다시 설치**했다.

- 실행일: 2026-11-04
- 원본: `/home/nstel/ti`
- 대상: `prodigyrcn@192.168.0.107`, `/home/prodigyrcn/ti`
- 대상 OS: Ubuntu 24.04.4 LTS, x86_64
- RAM: 약 32GB, 작업 전 가용 디스크 312GB, 설치/소스 복사 후 287GB
- CCS/Linux SDK/MCU+ SDK 설치 및 컴파일러 버전 실행 확인 완료
- GitHub의 상위 저장소 clone 완료. **원본 장비의 미커밋 작업과 로컬 소스 branch는 아직 이전되지 않았다.**
- SDK에서 복사한 Linux source에 패키지 변경이 있어 workspace 검증은 실패한다. 처리 방침 확인 전 소스 수정 및 전체 빌드를 보류했다.

이는 개발 호스트 준비 단계다. Boot ROM → SPL/U-Boot → Linux → rootfs → 서비스/주변장치 검증은 보드 연결 이후 진행한다.

## 대상 장비의 구성

```text
~/ti/
├── CCS_20.4.0.00013_linux.zip
├── CCS_20.4.0.00013_linux/             # 전송한 ZIP을 대상에서 해제
├── ccs2040/                          # 대상에서 신규 설치
│   └── ccs/utils/sysconfig_1.26.0/
├── gcc-arm-9.2-2019.12-x86_64-aarch64-none-elf.tar.xz
├── gcc-arm-9.2-2019.12-x86_64-aarch64-none-elf/
├── am64x/
│   ├── ti-processor-sdk-linux-am64xx-evm-12.00.00.07.04-Linux-x86-Install.bin
│   ├── ti-processor-sdk-linux-am64xx-evm-12.00.00.07.04/
│   ├── mcu_plus_sdk_am64x_12_00_00_27-linux-x64-installer.run
│   └── mcu_plus_sdk_am64x_12_00_00_27/
├── local_git_repo/                   # 생성만 완료, MCU+ seed 미이전
├── migration-logs/
└── TI_Bringup/
    ├── tools/env/*.env               # 두 .env.example에서 생성
    └── workspace/
        ├── ti-u-boot-sdk12/          # 새 SDK에서 복사
        └── ti-linux-kernel-sdk12/    # 새 SDK에서 복사
```

원본의 독립 `~/ti/sysconfig_1.26.0` 폴더는 이식하지 않았다. MCU+ 환경 템플릿이 사용하는 CCS 내장 SysConfig 1.26.0이 설치되어 있다. 원본 `am64x/build`, 상위 repo의 `out`, `deploy`, 별도 TF-A/OP-TEE 실험 workspace 등은 아직 옮기지 않았다. MCU+ workspace와 bare seed repo도 별도 이전 대상이다.

## 전송과 무결성

`rsync --partial --relative`로 파일 4개, 총 4,495,885,896 bytes를 전송했다. 다음 SHA-256은 양쪽 장비에서 일치했다. 이는 원본 장비와의 전송 무결성 확인이다.

| 패키지 | SHA-256 |
|---|---|
| `CCS_20.4.0.00013_linux.zip` | `80910ef3c5027ce9345add406b4a2e54f27fe6044aa5b81068eb2761c11c8e49` |
| `mcu_plus_sdk_am64x_12_00_00_27-linux-x64-installer.run` | `fd050363dcae6499f082fb24826f79e90d1bcc7656e8ce92790887a201722baa` |
| `ti-processor-sdk-linux-am64xx-evm-12.00.00.07.04-Linux-x86-Install.bin` | `b4700c20d8c94adee4d3455d20a802a4ea9d17529e2ac4f663eb7d448ca1dec2` |
| `gcc-arm-9.2-2019.12-x86_64-aarch64-none-elf.tar.xz` | `36d2cbe7c2984f2c20f562ac2f3ba524c59151adfa8ee10f1326c88de337b6d1` |

## SSH로 수행한 작업

### 호스트 패키지

`apt-get update` 후 다음 패키지를 설치했다. 설치 로그는 `~/ti/migration-logs/host-packages.log`다.

```text
build-essential git git-lfs rsync unzip xz-utils zip wget curl ca-certificates
file bc bison flex libssl-dev libelf-dev libncurses-dev swig device-tree-compiler
python3 python3-pip python3-venv python3-dev python3-serial python3-yaml
python3-pyelftools python3-setuptools cmake ninja-build pkg-config cpio gawk
diffstat chrpath socat texinfo zstd lz4 libusb-1.0-0 libusb-0.1-4 libgtk-3-0
libnss3 libasound2t64 libgbm1 libxss1 libxtst6 libatk-bridge2.0-0
libx11-xcb1 libsecret-1-0
```

최초 설치 시도에서 `libgconf-2-4`가 Ubuntu 24.04 저장소에 없어 실패했다. 해당 항목을 제외한 재실행은 성공했다. CCS 본체에 대한 `ldd` 결과에는 미해결 라이브러리가 없었다. 이 확인은 GUI 기동/디버거 연결 검증과 별개다.

### 패키지 설치

각 설치 프로그램의 `--help`에서 `--mode unattended`와 `--prefix`를 확인한 뒤 아래 방식으로 실행했다. 세 설치 프로그램 모두 종료 코드 0이었다. CCS는 기본 전체 component 선택을 사용했다.

```bash
cd ~/ti
unzip -q CCS_20.4.0.00013_linux.zip
chmod u+x CCS_20.4.0.00013_linux/ccs_setup_20.4.0.00013.run
./CCS_20.4.0.00013_linux/ccs_setup_20.4.0.00013.run \
  --mode unattended --prefix "$HOME/ti/ccs2040"

chmod u+x am64x/*Install.bin am64x/*installer.run
./am64x/ti-processor-sdk-linux-am64xx-evm-12.00.00.07.04-Linux-x86-Install.bin \
  --mode unattended \
  --prefix "$HOME/ti/am64x/ti-processor-sdk-linux-am64xx-evm-12.00.00.07.04"
./am64x/mcu_plus_sdk_am64x_12_00_00_27-linux-x64-installer.run \
  --mode unattended --prefix "$HOME/ti/am64x"

tar -xJf gcc-arm-9.2-2019.12-x86_64-aarch64-none-elf.tar.xz
sudo ~/ti/ccs2040/ccs/install_scripts/install_drivers.sh
sudo usermod -aG dialout prodigyrcn
```

TI permissions/Blackhawk/J-Link 설치 스크립트 성공과 `/etc/udev/rules.d/71-ti-permissions.rules`, `99-jlink.rules` 생성을 확인했다. 새 SSH 세션에서 `dialout` 그룹 포함도 확인했다. 기존 데스크톱 세션은 로그아웃/로그인 후 적용한다.

후속 workspace 재구성에서 MCU+ installer가 prefix 아래에 SDK 폴더명을 추가한다는 점을
확인했다. 최초의 SDK 이름까지 포함한 prefix는 중첩 설치를 만들었으므로, 위 명령을
부모 `~/ti/am64x` prefix로 정정하고 대상에서 원본 installer를 재실행했다.

### 도구 확인 결과

| 항목 | 결과 |
|---|---|
| Linux/A53 `aarch64-oe-linux-gcc` | GCC 15.2.0 실행 성공 |
| R5 `arm-oe-eabi-gcc` | GCC 15.2.0 실행 성공 |
| Bare-metal `aarch64-none-elf-gcc` | GCC 9.2.1 실행 성공 |
| `tiarmclang` | 4.0.4.LTS 실행 성공 |
| CCS 내장 SysConfig CLI | 1.26.0+4407 실행 성공 |
| Python `serial`, `yaml` | import 성공 |
| SDK prebuilt | `tiboot3.bin`, `tispl.bin`, `u-boot.img` 존재 확인 |

전체 U-Boot/kernel/MCU+ 빌드와 실제 보드 부팅은 미검증이다. SDK의 `setup.sh`를 통한 TFTP/NFS/보드 네트워크 설정도 아직 실행하지 않았다.

## Git 및 소스 준비 상태

대상에서 다음 저장소를 HTTPS로 clone했다.

```text
origin: https://github.com/KimKiYoun-nstel/TI_BringUP.git
branch: main
HEAD: 5fecbf52a13fc231071c85975a0bdece75ddc73c
```

원본의 상위 repo HEAD와 일치하며, 대상 상위 repo는 clean 상태였다. GitHub 쓰기 인증 및 사용자 identity 설정은 아직 준비하지 않았다.

다음 템플릿을 각각 같은 이름의 `.env`로 복사했다. `$HOME/ti` 기반이므로 새 사용자 경로를 따른다.

- `tools/env/sdk-12.00.00.07.04.env.example`
- `tools/env/mcu-plus-sdk-am64x-12.00.00.env.example`

`bash tools/prepare/create-workspace.sh` 실행은 성공했다. 다만 이 스크립트는 SDK source를 그대로 복사하므로 아래 상태가 함께 복사됐다.

| workspace | HEAD | 상태 |
|---|---|---|
| U-Boot | `2549829cc194ffd9e38b755d2e10c7fc4cd971eb` | `oe-gitpkgv_2549829cc194ffd9e38b755d2e10c7fc4cd971eb` 미추적 파일 |
| Linux | `c214492085504176b9c252a7175e4e60b4b442af` | 추적 파일 2개 수정 |

Linux 패키지 변경:

- `arch/arm/tools/gen-mach-types`: 생성 파일 주석에서 입력 파일명 제거
- `tools/perf/util/python.c`: `#include "sample.h"` 추가

실행한 확인 명령은 `bash ~/ti/TI_Bringup/tools/prepare/verify-workspace-state.sh`이며, Linux unstaged diff로 **종료 코드 1**이었다. U-Boot의 미추적 파일은 이 스크립트의 검사 범위 밖이다. baseline tag/topic branch 생성 전 strict clean 확인에서 중단했으므로 새 baseline tag/topic branch는 아직 만들지 않았다.

후속 조치는 승인 후 **workspace 사본에 한해** 패키지 변경을 diff로 보관하고 Git 기준 clean 상태를 만들거나, 원본 장비의 로컬 Git 이력을 이식하는 것이다. SDK 설치 원본은 유지한다.

추가 경로 점검: `tools/prepare/verify-workspace-state.sh`의 MCU+ 외부 변경 검사에는 `/home/nstel/ti/...`가 하드코딩되어 있다. 새 장비에서는 그 두 검사가 실제 MCU+ 설치 경로를 검사하지 못하므로, 경로 대응 전에는 검증 통과만으로 MCU+ 원본 무변경을 판단할 수 없다. 이번 작업에서는 해당 스크립트를 수정하지 않았다.

## 현재 작업까지 온전히 옮기기 위한 후속 작업

### 원격으로 가능한 항목

1. **상위 repo 미커밋 작업 보존**: 원본에 TSN/UART 관련 수정 및 신규 파일이 다수 있다. 검토 후 필요한 변경을 commit/push하고 대상에서 pull하거나, tracked diff와 선별한 untracked 파일을 별도 전달한다. `git diff HEAD --binary`에는 untracked 파일이 포함되지 않는다. commit/push는 이번에 수행하지 않았다.
2. **로컬 Git 이력 보존**: 원본 `workspace/*`는 상위 repo Git 관리 밖이다. 유지할 source repo별 `git bundle create <출력경로> --all` 또는 Git 원격 전송을 사용한다. bundle은 uncommitted/untracked 작업과 ignored build output을 담지 않으므로 각 repo의 `git status --short` 및 작업용 worktree 구성도 확인한다.
3. **MCU+ seed 이전**: 원본 `~/ti/local_git_repo/mcu_plus_sdk_am64x_12_00_00_27.git`와 MCU+ workspace의 선택 branch를 보존한다. 대상 `local_git_repo`는 현재 비어 있다. 설치 폴더를 복사하는 대신 이미 설치된 SDK와 로컬 Git 이력을 연결한다.
4. **추가 실험 source**: 원본에는 별도 U-Boot fullchain, TF-A/OP-TEE 및 diagnostic workspace가 있다. 각 상태를 확인하고 채택 patch 재적용 또는 Git 이력 이전 여부를 결정한다.
5. **로컬 자산 선별**: `.env`, 필요한 build output, firmware, prebuilt SD image, TFTP payload, ignored 설정/로그 등을 따로 점검한다. 원본 `~/ti/TI_Bringup_Repo_Setup_Agent_Guide.md`도 상위 Git clone에 포함되지 않는다.
6. **호스트별 연결 설정**: `tools/uart/targets.json`, board profile, `logs/runtime_log` 링크, TFTP/NFS 및 NIC 이름/IP를 새 네트워크에 맞춰 확인한다. UART는 기존 daemon TCP endpoint를 계속 쓸 수 있으면 물리 연결 없이 SSH로 점검 가능하다.
7. **추가 실행 환경**: 원본에서 사용하는 Node/.NET/OpenCode 등은 `~/ti` 설치 패키지 이전만으로 준비되지 않는다. 필요한 도구의 버전과 사용자별 설정을 확인해 별도 준비한다. Python 추가 패키지는 Ubuntu 24.04의 시스템 Python 대신 프로젝트 venv에서 관리한다.
8. **빌드 검증**: clean baseline/topic branch 확정 및 patch 선택 후 workspace 검증 → U-Boot R5/A53/TF-A/OP-TEE → kernel/DTB/modules → MCU+ 순으로 실제 build를 확인한다.

### 대상 장비에서 직접 조작이 필요한 항목

| 항목 | 현장 작업 | 이후 SSH로 가능한 검증 |
|---|---|---|
| CCS GUI | 데스크톱에서 `~/ti/ccs2040/ccs/theia/ccstudio` 최초 실행, workspace 선택, SDK/project 인식 확인 | 설치 로그/CLI 도구 확인 |
| USB/JTAG/UART | 케이블 연결, 권한 적용을 위한 재로그인 또는 USB 재연결, probe/serial 식별 | `lsusb`, `/dev/serial/by-id`, daemon 설정, JTAG/UART 통신 확인 |
| 보드 | 전원/boot strap/SD/OSPI/이더넷 및 TAP 연결 | 연결 후 UART MCP/SSH를 통한 boot/runtime 검증 |
| SD 등 매체 | 실제 장치 연결 및 매체 식별 | 장치 식별 후 승인된 image 기록/검증 |
| GitHub 인증 | 사용자 계정의 공개키/토큰 등록 및 로그인 승인 | 인증이 준비되면 fetch/pull/push 가능 |

GUI는 원격 데스크톱이 별도로 준비되어 있으면 원격 조작도 가능하다. GitHub 인증 등록은 대상 장비 현장 방문 없이도 사용자 브라우저에서 처리할 수 있다.

## 증적 및 다음 시작점

대상 `~/ti/migration-logs/`:

- `host-packages.log`
- `processor-sdk-install.log`, `mcu-plus-install.log`, `ccs-install.log` — 무인 installer stdout은 비어 있음
- `ccs-drivers.log`
- `git-clone.log`, `create-workspace.log`
- `verification.log` — 도구 버전, source 상태, workspace 검증 실패 및 CCS 라이브러리 확인

후속 감사에서 [Git 상태 및 작업 연속성 기준 마이그레이션 선별](2026-11-04_git-workspace-migration-audit.md)을 작성했다. 상위 Git 변경을 먼저 검토하고, 공식 patch로 재구성 가능한 source와 별도 보존할 로컬 정보(commit/diff/stash, raw 증적, golden image, 회로도/가이드)를 나누어 이전한다. 두 source 폴더는 새 SDK에서 복사한 초기 입력이며 원본 장비의 작업 상태를 이식한 결과가 아니다.
