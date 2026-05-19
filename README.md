# TI_BringUP

TI AM64x 계열 보드 브링업과 Embedded Linux BSP 개발을 위한 작업 저장소입니다.

이 저장소는 초기에는 문서 중심의 지식 저장소로 시작했지만, 현재는 TI Processor SDK Linux 12.00.00.07.04를 기준으로 실제 bring-up 개발을 반복하기 위한 로컬 BSP workspace, patch/config 관리, build/install helper, 보드별 기록을 함께 관리합니다.

핵심 원칙은 명확합니다. TI SDK 전체 source tree를 원격 Git repo에 올리지 않고, 로컬 `workspace/`에만 U-Boot/Linux kernel source tree를 둡니다. 장기 보관할 변경은 patch, config, DTS 후보, rootfs overlay, 문서, 로그, 스크립트 형태로 이 repo에 남깁니다.

## 현재 역할

- AM64x BSP bring-up 작업 공간
- U-Boot/Linux kernel source 분석 및 수정 workspace의 상위 관리 repo
- 자체 보드 포팅을 위한 patch/config/DTS/rootfs overlay 관리 repo
- 보드별 bring-up 로그, 결정사항, 실패 원인, 재현 절차를 남기는 지식 저장소
- AI Agent가 반복적으로 분석, 수정, 빌드, 기록 작업을 수행하기 위한 기준 repo

## 운영 원칙

- SDK 원본 경로 `~/ti/am64x/.../board-support/...`는 reference로만 사용합니다.
- 실제 U-Boot source는 `workspace/ti-u-boot-sdk12`에서 분석/수정합니다.
- 실제 Linux kernel source는 `workspace/ti-linux-kernel-sdk12`에서 분석/수정합니다.
- `workspace/`는 상위 repo Git에서 제외합니다.
- source tree 내부 변경은 workspace 내부 git branch/commit으로 관리합니다.
- 장기 보관할 변경은 `git format-patch`로 export하여 `bsp/*/patches/`에 저장합니다.
- 상위 repo에는 patch, config, DTS 후보, docs, scripts, rootfs overlay, 선별 로그만 commit합니다.
- 빌드 산출물, full rootfs, toolchain, SDK 전체 source, Yocto tmp/work/cache는 commit하지 않습니다.

## 문서 언어 원칙

- 이 저장소에서 새로 작성하거나 수정하는 문서는 기본적으로 한글로 작성합니다.
- 코드, 경로, 명령어, 로그 원문은 필요 시 원문 그대로 유지합니다.
- 영어 문서를 참조하더라도 설명, 판단 근거, 절차 정리는 한글을 기본으로 합니다.

## 기준 환경

| 항목 | 값 |
|---|---|
| Host | WSL2 / Ubuntu 계열 |
| SDK | TI Processor SDK Linux AM64x 12.00.00.07.04 |
| SDK Root | `~/ti/am64x/ti-processor-sdk-linux-am64xx-evm-12.00.00.07.04` |
| Bring-up Repo | `~/ti/TI_Bringup` |
| Workspace | `~/ti/TI_Bringup/workspace` |
| U-Boot Workspace | `workspace/ti-u-boot-sdk12` |
| Linux Workspace | `workspace/ti-linux-kernel-sdk12` |
| Baseline Tag | `ti-sdk-12.00.00.07.04-baseline` |

## Repository 구조

```text
TI_Bringup/
  README.md
  AI_AGENT_GUIDE.md
  PROJECT_BRIEF.md
  sdk-manifest/          # SDK version, source commits, baseline, build targets
  bsp/
    u-boot/              # U-Boot patches/configs/DTS candidates
    linux/               # Linux patches/configs/DTS candidates
  rootfs/                # RootFS overlay and notes only
  tools/
    env/                 # SDK env template and local env
    prepare/             # workspace creation and patch application
    build/               # build helper scripts
    install/             # install/deploy helper skeletons
  board/                 # board-specific working notes
  logs/                  # curated boot/U-Boot/kernel logs
  docs/                  # long-term knowledge base
  workspace/             # local only, ignored by parent Git
```

## 빠른 시작

```bash
cd ~/ti/TI_Bringup
cp tools/env/sdk-12.00.00.07.04.env.example tools/env/sdk-12.00.00.07.04.env
source tools/env/sdk-12.00.00.07.04.env
./tools/prepare/create-workspace.sh
```

Workspace baseline 확인:

```bash
git -C workspace/ti-u-boot-sdk12 status --short --branch
git -C workspace/ti-linux-kernel-sdk12 status --short --branch
git -C workspace/ti-u-boot-sdk12 tag --points-at HEAD
git -C workspace/ti-linux-kernel-sdk12 tag --points-at HEAD
```

## 일반 작업 흐름

```text
1. PROJECT_BRIEF.md와 AI_AGENT_GUIDE.md 확인
2. tools/env/*.env source
3. workspace clean 상태 확인
4. 필요한 경우 patch 적용
5. workspace 내부 source 분석/수정/빌드
6. 보드에서 boot/peripheral 동작 검증
7. workspace 내부 git commit 작성
8. format-patch로 bsp/*/patches/에 export
9. 문서, 로그, 결정사항 업데이트
10. 상위 TI_Bringup repo에 patch/docs/scripts만 commit
```

## 문서 위치

- `PROJECT_BRIEF.md`: 프로젝트 목적, 현재 상태, 범위, 기준 환경
- `AI_AGENT_GUIDE.md`: AI Agent 기본 작업 지침
- `sdk-manifest/`: SDK 버전, baseline, source commit, build target
- `docs/common/`: AM64x 공통 지식
- `docs/boards/`: 보드별 검증 결과와 고정 메모
- `docs/bringup-logs/`: 날짜별 실행 로그와 원본 증적
- `docs/setup/`: SDK, 툴체인, 호스트 환경 준비 절차
- `docs/research/`: 조사 중인 메모와 비교/가설 정리
- `docs/decisions/`: 채택한 결정과 근거
- `docs/tasks/`: 현재 작업 추적과 다음 액션

## 대상 보드

- TI SK-AM64B
- TI TMDS64EVM
- 추후 자체 개발 보드

## 커밋 대상 기준

Commit 대상:

- `bsp/u-boot/patches/*.patch`
- `bsp/linux/patches/*.patch`
- config fragment, defconfig 후보, DTS 후보
- rootfs overlay
- build/install/prepare scripts
- SDK manifest와 baseline 기록
- bring-up 로그 분석과 결정사항 문서

Commit 금지:

- `workspace/` 전체 source tree
- full SDK source tree
- 빌드 중간 산출물
- `.wic`, `.img`, `.dtb`, `.bin`, `.ko` 등 대형/생성 artifacts
- full rootfs unpacked tree
- toolchain/sysroot
