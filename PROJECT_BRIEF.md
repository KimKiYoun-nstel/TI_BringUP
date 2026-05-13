# Project Brief

## 프로젝트 목적

TI AM64x 계열 Evaluation Board(TMDS64EVM, SK-AM64B)를 이용하여 Embedded Linux BSP와 Board Bring-up 역량을 확보하고, 추후 자체 하드웨어 보드에서 필요한 U-Boot, Linux kernel, Device Tree, RootFS 포팅과 검증 절차를 수행할 수 있는 개발 기반을 만든다.

이 repo는 단순 문서 저장소가 아니라 실제 bring-up 작업 repo이다. 문서, patch, config, DTS 후보, rootfs overlay, build/install helper, 로컬 BSP workspace 운용 규칙을 함께 관리한다.

## 현재 Repo 역할

- TI Processor SDK Linux AM64x 12.00.00.07.04 기반 BSP 작업 기준점 관리
- U-Boot/Linux kernel source tree를 로컬 `workspace/`에 배치하고 분석/수정/빌드
- SDK 원본 변경을 피하고 workspace에서 실험 후 patch로 export
- 자체 보드 포팅에 필요한 board-specific delta를 patch/config/docs로 축적
- 부팅 실패, peripheral probe 실패, kernel panic, rootfs mount 실패 등 bring-up 이슈의 로그와 판단 근거 기록
- AI Agent가 반복 가능한 방식으로 workspace 확인, source 분석, 수정, 빌드, 문서화를 수행하도록 지침 제공

## 기준 환경

| 항목 | 값 |
|---|---|
| Host OS | WSL2 / Ubuntu 계열 |
| SoC Family | TI AM64x |
| SDK | TI Processor SDK Linux AM64x 12.00.00.07.04 |
| SDK Root | `~/ti/am64x/ti-processor-sdk-linux-am64xx-evm-12.00.00.07.04` |
| Bring-up Repo | `~/ti/TI_Bringup` |
| Local BSP Workspace | `~/ti/TI_Bringup/workspace` |
| U-Boot Workspace | `workspace/ti-u-boot-sdk12` |
| Linux Workspace | `workspace/ti-linux-kernel-sdk12` |
| Workspace Baseline Tag | `ti-sdk-12.00.00.07.04-baseline` |
| Target Boards | SK-AM64B, TMDS64EVM, custom board |
| Debug Interface | UART first, JTAG if needed |

## Source 관리 정책

- TI SDK 전체 source tree는 이 repo에 commit하지 않는다.
- `workspace/`는 local only이며 상위 Git에서 ignore한다.
- SDK 원본 `board-support/` source는 reference로만 사용한다.
- 실제 수정은 `workspace/ti-u-boot-sdk12`와 `workspace/ti-linux-kernel-sdk12`에서 수행한다.
- workspace 내부 git에서 branch/commit을 만들고, 장기 보관할 변경은 `git format-patch`로 export한다.
- 상위 repo에는 patch, config, DTS 후보, rootfs overlay, scripts, docs, 선별 로그만 commit한다.

## 범위에 포함

- Boot ROM / SPL / U-Boot / Linux Kernel / Device Tree / RootFS 부팅 흐름 이해
- TI SDK 기반 U-Boot와 Linux kernel standalone 분석/빌드
- U-Boot R5/A53 boot flow, boot media, bootcmd, environment 분석
- Linux Device Tree, pinctrl, clocks, resets, regulators, GPIO, PHY, MMC, UART, I2C, Ethernet bring-up
- RootFS overlay, systemd service, network config, firmware/module 배치
- 보드별 boot log, U-Boot log, kernel dmesg 분석
- 레퍼런스 보드와 자체 보드 간 HW delta 정리
- 재현 가능한 patch/config/docs 기반 BSP 변경 관리

## 범위에서 제외 또는 후순위

- MCU bare-metal/RTOS 개발
- 애플리케이션 서비스 개발
- 양산 테스트 자동화
- 회로 설계 자체
- SDK 전체 mirror repo 운영
- Yocto full build 환경 최적화는 필요 시 후순위로 검토

## 현재 상태

- [x] TI_Bringup repo 문서 기반 초기 지식 저장소 구성
- [x] TI Processor SDK Linux AM64x 12.00.00.07.04 설치 경로 확인
- [x] U-Boot/Linux kernel local workspace 생성
- [x] workspace baseline tag 설정
- [x] patch/config/docs/scripts 중심 repo 구조 생성
- [ ] Linux kernel build script의 정확한 TI SDK defconfig/build flow 검증
- [ ] U-Boot R5/A53 build script를 검증된 수동 절차 기준으로 구현
- [ ] SD card bootloader/kernel install script를 실제 partition layout 기준으로 구현
- [ ] SK-AM64B 기준 clean rebuild/boot 검증
- [ ] TMDS64EVM 기준 clean rebuild/boot 검증
- [ ] 자체 보드 HW delta checklist 작성
- [ ] 첫 custom board DTS/defconfig patch set 작성

## 기본 작업 흐름

```text
1. repo 상태 확인
2. env source
3. workspace 상태와 baseline 확인
4. 필요한 patch 적용 또는 새 branch 생성
5. source 분석/수정/빌드
6. 보드 검증
7. workspace 내부 commit
8. format-patch export
9. docs/logs/decisions/tasks 업데이트
10. 상위 repo commit
```

## 열린 질문

- [ ] Linux kernel standalone build에서 사용할 정확한 TI defconfig는 무엇인가?
- [ ] U-Boot SDK 12.00.00.07.04의 최종 R5/A53 build command와 artifact packaging 절차는 무엇인가?
- [ ] SK-AM64B와 TMDS64EVM 각각의 verified boot media와 partition layout은 무엇인가?
- [ ] 우선 bring-up할 peripheral 순서는 무엇인가?
- [ ] 자체 보드에서 레퍼런스 보드와 달라질 가능성이 큰 HW 항목은 무엇인가?
