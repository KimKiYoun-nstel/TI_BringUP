# AI Agent Guide

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
- Patch/config/docs 관리 담당자

## 반드시 먼저 확인할 파일

작업 시작 시 다음 파일을 우선 확인한다.

```text
PROJECT_BRIEF.md
AI_AGENT_GUIDE.md
README.md
sdk-manifest/workspace-baseline.md
sdk-manifest/source-commits.md
```

작업이 보드별 이슈라면 추가로 확인한다.

```text
docs/boards/<board-name>/
docs/bringup-logs/
docs/tasks/TASK_BOARD.md
docs/decisions/DECISION_LOG.md
```

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

관리하지 않는 대상:

- TI SDK 전체 source tree
- `workspace/` 전체 source tree
- full rootfs unpacked tree
- toolchain/sysroot
- Yocto tmp/work/cache
- 대형 build artifacts

## BSP Workspace 규칙

- SDK 원본 경로 `~/ti/am64x/.../board-support/...`는 reference로만 사용하고 직접 수정하지 않는다.
- 실제 U-Boot source는 `workspace/ti-u-boot-sdk12`에서 분석/수정한다.
- 실제 Linux kernel source는 `workspace/ti-linux-kernel-sdk12`에서 분석/수정한다.
- `workspace/`는 상위 repo Git에서 제외한다.
- source tree 실험 변경은 workspace 내부 git branch/commit으로 관리한다.
- 장기 보관할 변경은 `git format-patch`로 export하여 `bsp/u-boot/patches/` 또는 `bsp/linux/patches/`에 저장한다.
- 상위 repo에는 patch, config, DTS 후보, docs, scripts, rootfs overlay, 선별 로그만 commit한다.
- `tools/prepare/apply-*-patches.sh`는 workspace를 reset/clean하므로 실행 전 workspace 내부 미보관 변경이 없는지 확인한다.

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
```

Workspace가 dirty이면 이유를 먼저 확인한다. 사용자가 만든 변경일 수 있으므로 임의로 되돌리지 않는다. 단, 사용자가 명시적으로 clean baseline 복원을 지시한 경우에만 reset/clean을 수행한다.

## Source 수정 원칙

- SDK 원본을 직접 수정하지 않는다.
- workspace 내부에서 topic branch를 만든다.
- 변경 전 baseline과 현재 branch를 명확히 확인한다.
- DTS/defconfig 변경은 가능하면 새 board 파일을 추가하는 방식으로 진행한다.
- TI EVM 원본 파일 수정은 불가피할 때만 수행하고 patch를 분리한다.
- 변경 후 workspace 내부에서 commit한다.
- 상위 repo에는 workspace commit 자체가 아니라 `format-patch` 결과를 저장한다.

예시:

```bash
cd ~/ti/TI_Bringup/workspace/ti-linux-kernel-sdk12
git switch -c nstel/myboard-dts ti-sdk-12.00.00.07.04-baseline
# edit source
git diff
git add <files>
git commit -m "arm64: dts: ti: add NSTEL AM64x board"
git format-patch ti-sdk-12.00.00.07.04-baseline..HEAD -o ~/ti/TI_Bringup/bsp/linux/patches/
```

## Build 작업 원칙

- build script가 skeleton이면 skeleton이라고 명확히 말한다.
- 검증되지 않은 build command를 확정 절차처럼 문서화하지 않는다.
- build 실패 시 command, environment, failing target, first error, relevant log path를 남긴다.
- U-Boot는 AM64x boot flow상 R5 SPL, A53 SPL/U-Boot proper, TF-A, OP-TEE, SYSFW/TIFS/DM firmware 의존성을 함께 고려한다.
- Linux kernel은 `ARCH=arm64`, cross compiler prefix, defconfig, DTB target, modules install path를 명확히 구분한다.

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

## 저장소 디렉터리 기준

| 문서/폴더 | 용도 |
|---|---|
| `PROJECT_BRIEF.md` | 프로젝트 목적, 범위, 현재 상태 |
| `README.md` | repo 역할, 구조, 빠른 시작 |
| `sdk-manifest/` | SDK 버전, source commit, workspace baseline, build target |
| `bsp/u-boot/` | U-Boot patch/config/DTS 후보 |
| `bsp/linux/` | Linux patch/config/DTS 후보 |
| `rootfs/` | rootfs overlay와 설정 조각 |
| `tools/` | env, prepare, build, install helper |
| `board/` | 현재 작업용 보드별 메모 |
| `logs/` | 선별 보관하는 boot/U-Boot/kernel 로그 |
| `docs/` | 장기 지식 베이스 |
| `workspace/` | local only source workspace, 상위 Git ignore |

## 답변/작업 원칙

1. 보드 부팅 흐름 안에서 작업을 설명한다.
2. 어떤 파일을 왜 수정하는지 명확히 말한다.
3. 로그에서 봐야 할 포인트와 실패 시 의심 지점을 함께 제시한다.
4. 확정/추정/확인 필요를 구분한다.
5. 기존 결정사항과 충돌하면 먼저 보고한다.
6. 코드나 설정 변경 시 관련 문서도 함께 업데이트한다.
7. 사용자가 명시적으로 요청하지 않은 destructive 작업은 하지 않는다.
8. workspace 또는 SDK source의 예상 밖 dirty 상태를 발견하면 멈추고 사용자에게 확인한다.

## 작업 후 정리 형식

중요한 작업 후에는 필요한 항목만 골라 다음 형식으로 정리한다.

```md
## Knowledge
- 새로 이해한 개념 또는 배경지식

## Decision
- 결정한 사항
- 이유
- 영향 범위

## Assumption
- 현재 전제로 둔 사항

## Action Item
- 다음 작업

## Open Question
- 추가 확인이 필요한 항목

## Board Note
- 특정 보드에만 해당하는 내용

## Artifact
- 생성된 patch, config, log, script, image 경로
```

## 커밋 메시지 가이드

```text
repo: add SDK12 workspace management structure
bsp: add Linux board DTS patch
bsp: add U-Boot NSTEL defconfig patch
docs: record SK-AM64B boot validation
tools: add AM64x kernel build helper
logs: add SK-AM64B kernel boot failure analysis
```

## 금지/주의 사항

- 확인되지 않은 내용을 확정처럼 쓰지 않는다.
- 보드별 차이를 AM64x 공통 사실처럼 일반화하지 않는다.
- SDK 버전, board revision, boot mode가 불명확하면 확인 필요로 표시한다.
- 실제 하드웨어 변경이 필요한 내용을 SW 설정만으로 해결 가능하다고 단정하지 않는다.
- full SDK source, workspace source tree, build artifacts를 상위 repo에 추가하지 않는다.
- local env 파일의 개인 경로를 불필요하게 commit하지 않는다.
