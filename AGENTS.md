# AGENTS Guide

이 문서는 ChatGPT, Codex, Copilot, 또는 외부 AI Agent가 이 저장소에서 작업할 때 따라야 하는 기본 지침이다.

## Agent의 기본 역할

이 저장소는 TI AM64x Embedded Linux BSP와 board bring-up을 위한 실제 작업 repo이다. Agent는 단순 문서 정리자가 아니라 bring-up 개발 보조자 역할을 수행한다.

Agent는 다음 관점으로 판단한다.

- Embedded Linux BSP Engineer
- Board Bring-up Engineer
- U-Boot / SPL 분석자
- Linux kernel / Device Tree 분석자
- RootFS / service / firmware 배치 검토자
- Boot log, U-Boot log, kernel dmesg 기반 failure 분석자
- UART runtime boot log 기반 failure 분석자
- Patch/config/docs 관리 담당자

## 반드시 먼저 확인할 파일

작업 시작 시 다음 파일을 우선 확인한다.

```text
PROJECT_BRIEF.md
AGENTS.md
README.md
sdk-manifest/workspace-baseline.md
sdk-manifest/source-commits.md
sdk-manifest/workspaces.yml
```

커스텀 보드 DTS 재구성 또는 custom board image build 연동 작업이면 다음도 우선 확인한다.

```text
docs/common/CUSTOM_BOARD_DTS_WORKFLOW.md
tools/custom_board_dts_workflow/README.md
tools/custom_board_dts_workflow/docs/workflow_guide.md
tools/custom_board_dts_workflow/platforms/am64x/projects/cpu_brd_v03_pba_260511/
```

작업이 보드별 이슈라면 추가로 확인한다.

```text
docs/boards/<board-name>/
docs/bringup-logs/
docs/tasks/TASK_BOARD.md
docs/decisions/DECISION_LOG.md
docs/common/ISSUE_RESOLUTION_WORKFLOW.md
```

보드의 reboot 전후 동작, early boot 흐름, UART에서 직접 보이는 runtime 증적을 판단해야 하는 작업이라면 다음 로그를 우선 확인한다.

```text
logs/runtime_log
```

`logs/runtime_log`는 board의 UART terminal 로그와 동기화된 링크 파일로 간주한다. 따라서 kernel boot, reboot 직후 상태, early service startup timing, panic/crash 직전후 출력처럼 **UART에서 직접 보이는 boot/runtime 증적**이 필요할 때 이 파일을 우선 reference로 사용한다. UART 관련 판단의 기준 로그는 항상 `logs/runtime_log`다. 반대로 OS 부팅 이후의 일반적인 steady-state 동작 분석은 SSH, systemd journal, `/sys`, `dmesg`, 서비스 상태, 애플리케이션 출력 등을 함께 본다.

reboot 이후 UART 출력 감시, autoboot 중단, U-Boot prompt 진입, boot command 검증, Linux prompt 확인처럼 **UART 상호작용 자체를 재현하거나 자동화**해야 하는 작업은 daemon 기준 구조를 사용한다.

- `tools/uart/uartd.py`: UART port owner daemon
- `tools/uart/uartctl.py`: 사람 또는 로컬 script가 직접 사용하는 CLI
- `tools/uart/uart-mcp-server.py`: Agent가 사용하는 MCP adapter

구조와 사용 절차의 상세 설명은 `docs/common/UART_DAEMON_AGENT_WORKFLOW.md`를 우선 참고한다.

## UART 사용 원칙

이 프로젝트에서 UART 사용 원칙은 다음과 같다.

1. UART 로그의 기준은 항상 `logs/runtime_log`다.
2. UART를 통한 boot log 확인과 입출력 상호작용은 기본적으로 `uart` MCP 서버를 사용한다.
3. MCP server 제공 tool의 기능 제약 때문에 작업을 계속 진행할 수 없을 때만 `uartctl.py`를 직접 사용한다.
4. UART port는 오직 `uartd.py`만 직접 연다. Agent와 사용자는 모두 `uartd`를 통해 같은 세션을 공유한다.

## UART MCP 사용 지침

이 프로젝트에서는 실제 보드 UART 콘솔이 `uart` MCP 서버를 통해 제공될 수 있다.

다음 작업에는 UART MCP tool을 우선 사용한다.

- 보드 부팅 로그 확인
- U-Boot prompt 확인 및 명령 실행
- Linux login / shell 상태 확인
- 커널 로그, rootfs, network 상태 확인
- 실제 보드 serial console에서 명령 실행이 필요한 경우

사용 기준:

1. 현재 콘솔 상태가 불명확하면 먼저 `uart_tail`을 사용한다.
2. U-Boot prompt는 `=> `, Linux root shell prompt는 `# `, login prompt는 `login:`을 기준으로 판단한다.
3. 일반 명령은 `uart_command`를 사용한다.
4. 입력만 필요하면 `uart_sendline`을 사용한다.
5. 출력만 기다릴 때는 `uart_expect`를 사용한다.
6. timeout이 발생하면 같은 명령을 반복하지 말고 `uart_tail`로 최근 출력을 다시 확인한다.
7. 사람이 `uartctl attach`를 보고 있어도 MCP write는 허용된다. 다만 동시 입력 충돌은 사용자가 판단한다.

## UART CLI fallback 지침

다음 상황에서는 MCP 대신 `uartctl.py`를 직접 사용할 수 있다.

- MCP tool에 아직 없는 기능이 필요한 경우
- raw interactive console이 필요한 경우
- read-only live console을 사람이 직접 보고 싶은 경우
- MCP adapter 또는 opencode MCP 연결 상태를 분리해서 진단해야 하는 경우

대표 명령:

- `./tools/uart/uartctl.py status`
- `./tools/uart/uartctl.py tail`
- `./tools/uart/uartctl.py watch`
- `./tools/uart/uartctl.py attach`
- `./tools/uart/uartctl.py send ...`
- `./tools/uart/uartctl.py command ... --expect ...`

다만 CLI fallback을 사용하더라도 판단 기준 로그는 여전히 `logs/runtime_log`다.

## Repository의 현재 성격

초기 repo는 문서 중심 지식 저장소였지만, 현재는 실제 bring-up 개발 환경을 포함한다.

관리 대상:

- 문서와 결정사항
- SDK manifest와 workspace baseline
- U-Boot/Linux kernel patch set
- config fragment, defconfig 후보
- DTS 후보와 board-specific note
- rootfs overlay
- build/install/prepare scripts
- 선별된 boot/U-Boot/kernel 로그
- provenance와 rehearsal audit 기록

## 문서 작성 규칙

- 이 저장소에 새로 추가하거나 수정하는 Markdown 문서는 **기본적으로 한글로 작성한다.**
- 코드, 경로, 명령어, 환경변수, 로그 원문은 필요 시 원문 그대로 유지한다.
- 영어 자료를 인용할 때도 문서 본문 설명과 판단 근거는 한글로 정리한다.
- 작업 히스토리, 의사결정, 보드 메모, setup 가이드는 모두 한글을 기본 언어로 사용한다.
- 실험성 문서라도 특별한 이유가 없으면 영문이 아니라 한글을 기본으로 한다.

## 관리하지 않는 대상

- TI SDK 전체 source tree
- `workspace/` 전체 source tree
- full rootfs unpacked tree
- toolchain/sysroot
- Yocto tmp/work/cache
- 대형 build artifacts

## BSP Workspace 규칙

- SDK 원본 경로 `~/ti/am64x/.../board-support/...`는 reference로만 사용하고 직접 수정하지 않는다.
- **현재 workspace 외부의 SDK 원본, toolchain, sysroot, live SD/OSPI 내용은 사용자 승인 없이 절대 수정하지 않는다.**
- 실제 U-Boot source는 `workspace/ti-u-boot-sdk12`에서 분석/수정한다.
- 실제 Linux kernel source는 `workspace/ti-linux-kernel-sdk12`에서 분석/수정한다.
- MCU+ SDK 수정이 필요하면 외부 SDK 원본이 아니라 재현 가능한 workspace/patch 흐름을 먼저 만든다.
- `workspace/`는 상위 repo Git에서 제외한다.

## Workspace 운영 모델

이 저장소는 **혼합 모델**을 사용한다.

### 1. workspace 내부

- `workspace/*`는 실험/리허설을 수행하는 editable local git repo이다.
- baseline branch에서 직접 실험하지 말고 local topic branch를 만든다.
- branch 예:
  - `phase2-button-event`
  - `phase2-boot-rm`
  - `custom-board-audio`
- local branch는 실험 전환, 비교, merge 검토를 쉽게 하기 위한 1차 운영 단위다.

### 2. Main Repo 내부

- Main Repo는 공식 형상 owner이다.
- workspace 변경 중 장기 보관 가치가 있는 것은 다음으로 반입한다.
  - `bsp/*/patches/`
  - `sdk-manifest/`
  - `logs/provenance/`
  - `docs/research/`, `docs/decisions/`, `docs/tasks/`

### 3. 채택 규칙

- workspace 변경은 자동으로 최종 output baseline에 누적되지 않는다.
- `series`에 포함된 patch만 replay 대상이다.
- patch로 승격되지 않은 변경은 provenance/research에 참고 자산으로만 남긴다.
- branch는 실험 단위이고, patch/provenance는 공식 기록 단위다.

## 작업 전 체크리스트

```bash
cd ~/ti/TI_Bringup
pwd
git status --short
source tools/env/sdk-12.00.00.07.04.env
[ -d "$SDK_ROOT" ] && echo "SDK OK: $SDK_ROOT"
[ -d "$UBOOT_SRC/.git" ] && echo "U-Boot workspace OK: $UBOOT_SRC"
[ -d "$KERNEL_SRC/.git" ] && echo "Kernel workspace OK: $KERNEL_SRC"
git -C "$UBOOT_SRC" status --short --branch
git -C "$KERNEL_SRC" status --short --branch
bash tools/prepare/verify-workspace-state.sh
```

Workspace가 dirty이면 이유를 먼저 확인한다. 사용자가 만든 변경일 수 있으므로 임의로 되돌리지 않는다. 단, 사용자가 명시적으로 clean baseline 복원을 지시한 경우에만 reset/clean을 수행한다.

## Source 수정 원칙

- 외부 SDK 원본을 직접 수정하지 않는다.
- workspace 내부에서 topic branch를 만든다.
- 변경 전 baseline과 현재 branch를 명확히 확인한다.
- DTS/defconfig 변경은 가능하면 새 board 파일을 추가하는 방식으로 진행한다.
- TI EVM 원본 파일 수정은 불가피할 때만 수행하고 patch를 분리한다.
- meaningful change는 workspace 내부 commit 또는 최소 patch export 가능 상태로 정리한다.
- 상위 repo에는 workspace commit 자체가 아니라 `format-patch` 결과, series, manifest, provenance를 저장한다.

## Build 작업 원칙

- build script가 skeleton이면 skeleton이라고 명확히 말한다.
- 검증되지 않은 build command를 확정 절차처럼 문서화하지 않는다.
- build 실패 시 command, environment, failing target, first error, relevant log path를 남긴다.
- U-Boot는 AM64x boot flow상 R5 SPL, A53 SPL/U-Boot proper, TF-A, OP-TEE, SYSFW/TIFS/DM firmware 의존성을 함께 고려한다.
- Linux kernel은 `ARCH=arm64`, cross compiler prefix, defconfig, DTB target, modules install path를 명확히 구분한다.
- build/deploy 전에는 `tools/prepare/verify-workspace-state.sh`를 통과해야 한다.

## Bring-up 분석 기준

모든 이슈는 부팅 흐름의 어느 단계인지 먼저 분류한다.

```text
Boot ROM
  -> tiboot3.bin
  -> tispl.bin
  -> u-boot.img
  -> Linux Image/DTB load
  -> Kernel boot
  -> rootfs mount
  -> systemd/services
  -> application/peripheral validation
```

분석 시 항상 다음을 구분한다.

- 확정된 사실
- 로그로 확인된 증거
- 합리적 추정
- 확인 필요 항목
- 다음 실험

## 문서 업데이트 기준

작업 후 장기 보관 가치가 있으면 문서에 반영한다.

- 결정사항: `docs/decisions/DECISION_LOG.md`
- 현재 작업 상태: `docs/tasks/TASK_BOARD.md`
- 보드별 고정 메모: `docs/boards/<board-name>/`
- 날짜별 실행 로그와 분석: `docs/bringup-logs/`
- 공통 개념: `docs/common/`
- SDK/source baseline: `sdk-manifest/`
- board-specific working notes: `board/<board-name>/`
- 실험 provenance: `logs/provenance/`

## 답변/작업 원칙

1. 보드 부팅 흐름 안에서 작업을 설명한다.
2. 어떤 파일을 왜 수정하는지 명확히 말한다.
3. 로그에서 봐야 할 포인트와 실패 시 의심 지점을 함께 제시한다.
4. 확정/추정/확인 필요를 구분한다.
5. 기존 결정사항과 충돌하면 먼저 보고한다.
6. 코드나 설정 변경 시 관련 문서도 함께 업데이트한다.
7. 사용자가 명시적으로 요청하지 않은 destructive 작업은 하지 않는다.
8. workspace 또는 SDK source의 예상 밖 dirty 상태를 발견하면 멈추고 사용자에게 확인한다.
9. workspace 외부 경로 수정은 사용자 승인 없이는 금지다.
