# TI_BringUP

TI AM64x 계열 보드 브링업과 Embedded Linux BSP 개발을 위한 작업 저장소입니다.

이 저장소는 초기에는 문서 중심의 지식 저장소로 시작했지만, 현재는 TI Processor SDK Linux 12.00.00.07.04를 기준으로 실제 bring-up 개발을 반복하기 위한 로컬 BSP workspace, patch/config 관리, build/install helper, 보드별 기록을 함께 관리합니다.

핵심 원칙은 명확합니다. TI SDK 전체 source tree를 원격 Git repo에 올리지 않고, 로컬 `workspace/`에만 U-Boot/Linux kernel source tree를 둡니다. 장기 보관할 변경은 patch, config, DTS 후보, rootfs overlay, 문서, 로그, 스크립트 형태로 이 repo에 남깁니다.

## 이 저장소를 어떻게 봐야 하는가

이 repo는 **source mirror**가 아니라 다음 세 가지를 묶어 관리하는 상위 저장소입니다.

1. **기준점 정의**
   - 어떤 SDK baseline에서 출발하는지
   - 어떤 보드/부트 경로를 현재 채택 상태로 볼지

2. **재현 자산 관리**
   - U-Boot / kernel workspace 변경 중 replay 가치가 있는 것들을
     `patch`, `config`, `DTS`, `helper script`로 승격

3. **실험 이력 관리**
   - 실패/성공 실험
   - bring-up 로그
   - 판단 근거
   - 다음 액션

즉, 실제 source 수정은 `workspace/`에서 일어나지만,
**장기적으로 남겨야 할 정보와 재현 수단은 이 repo가 관리**합니다.

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

추가 원칙:

- **`workspace/`는 현재 repo의 git 관리 대상이 아닙니다.**
- workspace 내부 git branch는 로컬 실험 단위이며, push 대상이 아닙니다.
- 새 작업은 가능하면 **TI SDK baseline clean tree**에서 다시 시작하고,
  repo 안의 patch/config/DTS/script를 선택 적용하는 방식으로 진행합니다.
- 즉 workspace working tree는 임시 실험 공간이고,
  repo는 **공식 기록과 재현 자산의 owner**입니다.

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
  AGENTS.md
  PROJECT_BRIEF.md
  sdk-manifest/          # SDK version, source commits, baseline, build targets
  bsp/
    u-boot/              # U-Boot patch series, config fragments, DTS candidates
    linux/               # Linux patch series, config fragments, DTS candidates
  rootfs/                # RootFS overlay / initramfs experiment sources
  tools/
    env/                 # SDK env template and local env
    prepare/             # workspace creation and patch application
    build/               # reproducible build helper scripts
    install/             # deploy/install/rehearsal helper scripts
    uart/                # host-side UART automation helpers for reboot/U-Boot/Linux flows
  board/                 # board-specific working notes
  logs/                  # curated boot/U-Boot/kernel logs + provenance
  docs/                  # long-term knowledge base and research notes
  workspace/             # local only, ignored by parent Git
```

실무적으로는 다음처럼 이해하면 됩니다.

- `workspace/`
  - 실제 수정/빌드/실험이 일어나는 local worktree
- `bsp/*/patches/series`
  - clean baseline에 replay 가능한 공식 patch 목록
- `docs/research/`
  - 아직 채택 전인 실험/가설/비교 기록
- `logs/provenance/`
  - 어떤 source 상태로 무엇을 빌드/배포했는지 기록

## UART 활용 Agent

이 저장소는 bring-up 과정에서 UART를 1차 증적 채널로 사용한다. 따라서 reboot 직후 boot log 관찰, autoboot 중단, U-Boot prompt 진입, boot command 검증, Linux login prompt 확인처럼 UART에서 직접 확인되는 흐름을 자동화할 수 있어야 한다.

`tools/uart/` 아래에는 host 측에서 실행하는 Python 기반 UART daemon / client helper를 둔다.

- `tools/uart/uartd.py`: UART port owner daemon
- `tools/uart/uartctl.py`: daemon client CLI
- `tools/uart/uart-mcp-server.py`: MCP stdio adapter for agents

이 helper들은 `pyserial`을 사용해 `/dev/ttyUSB*` 포트를 직접 감시하고 입력을 전송한다. 기본 모델은 `uartd.py`가 UART port를 계속 점유하고, `uartctl.py`가 Unix domain socket을 통해 daemon에 접속해 제어하는 구조다. 이 방식은 사람이 `tail`로 출력을 보면서 다른 Agent가 `send`/`expect`를 수행하는 workflow에 적합하다.

Agent 연동은 `uart-mcp-server.py`를 통해 수행한다. 이 adapter는 UART를 직접 열지 않고 `uartd.sock` JSON API만 호출하며, 프로젝트 루트의 `opencode.jsonc`에서 local MCP 서버로 등록할 수 있다.

원칙:

- UART helper는 `logs/runtime_log`와 같은 UART 증적 수집 흐름을 보조하는 도구다.
- helper가 자동화를 수행하더라도 최종 판단은 boot/U-Boot/kernel/runtime 로그를 직접 확인해 내려야 한다.
- 보드별 bring-up 절차가 고정되면 `tools/uart/*.json` plan 또는 board 문서에서 재사용 가능한 시나리오로 관리할 수 있다.

상세 구조와 daemon/client 사용 절차는 [docs/common/UART_DAEMON_AGENT_WORKFLOW.md](/home/nstel/ti/TI_Bringup/docs/common/UART_DAEMON_AGENT_WORKFLOW.md)를 참고한다.

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
1. PROJECT_BRIEF.md와 AGENTS.md 확인
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

현재 repo 운영에서 특히 중요한 단계는 다음 둘입니다.

1. **workspace diff를 바로 다음 작업의 기준으로 삼지 않기**
2. **필요한 변경만 repo-managed asset로 승격하기**

즉,

```text
clean baseline workspace
  + repo patch/config/DTS/script
  = 재현 가능한 작업 상태
```

를 만드는 것이 목표입니다.

## 자산 관리 기준

이 repo의 boot/bring-up 자산은 크게 세 가지로 관리합니다.

1. **채택 유지**
   - 현재 성공 경로 또는 baseline 이해에 직접 필요한 자산
2. **실험 자산이지만 보관 가치 있음**
   - 최종 경로에는 직접 안 쓰여도 원인 분석/회귀 비교에 중요한 자산
3. **legacy / 재검토 필요**
   - 현재 선택한 경로와 다른 가정을 전제로 한 옛 실험 자산

자세한 기준은 [BOOT_ASSET_CLASSIFICATION_GUIDE.md](/home/nstel/ti/TI_Bringup/docs/common/BOOT_ASSET_CLASSIFICATION_GUIDE.md)를 참고합니다.

최근 실제 적용 예시는 [2026-06-01_sk-am64b_boot-asset-inventory.md](/home/nstel/ti/TI_Bringup/docs/research/2026-06-01_sk-am64b_boot-asset-inventory.md)에 정리되어 있습니다.

## 현재 부트 경로 관점의 큰 틀

현재 repo에서 구분하는 대표 경로는 다음 둘입니다.

1. **SD baseline**
   - TI-style `env` 기반 SD-first boot
2. **USB-specific path**
   - 실험을 통해 확보한 USB-first / USB-only boot path

중요한 점은,
USB 성공 경로는 단순 media 교체가 아니라
**patch + media layout + boot policy** 의 조합이라는 것입니다.

관련 종합 정리는 [2026-06-01_sk-am64b_sd-vs-usb-boot-status.md](/home/nstel/ti/TI_Bringup/docs/research/2026-06-01_sk-am64b_sd-vs-usb-boot-status.md)를 참고합니다.

## 문서 위치

- `PROJECT_BRIEF.md`: 프로젝트 목적, 현재 상태, 범위, 기준 환경
- `AGENTS.md`: Agent 기본 작업 지침
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
- initramfs source / helper
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

다시 강조하면:

```text
workspace 내부 branch/commit = 로컬 실험 단위
repo commit/push            = 공식 기록/재현 자산 단위
```

입니다.
