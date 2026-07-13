# Decision Log

프로젝트에서 확정한 중요한 판단을 기록합니다.

## 작성 규칙

- “일단 이렇게 하자” 수준이라도 작업 방향에 영향을 주면 기록합니다.
- 결정 이유와 영향 범위를 남깁니다.
- 나중에 바뀔 수 있으면 재검토 조건을 적습니다.

---

## D-001. 프로젝트 지식 저장소를 Git repo로 관리한다

- 날짜: 2026-04-30
- 상태: Accepted
- 배경:
  - ChatGPT Project 안의 대화만으로는 장기 히스토리와 재사용 가능한 가이드를 안정적으로 관리하기 어렵다.
  - 개발자에게 익숙한 Git 기반 변경 이력을 활용한다.
- 결정:
  - `TI_BringUP` repo를 TI AM64x BSP/Board Bring-up 지식 저장소로 사용한다.
- 영향:
  - 대화에서 나온 장기 보관 항목은 Markdown 문서로 승격한다.
  - 보드별 bring-up 기록과 결정사항을 repo에 누적한다.
- 재검토 조건:
  - 문서 규모가 커져 별도 Wiki/문서 시스템이 필요해질 때

## D-002. Host 개발 환경은 Ubuntu 22.04 WSL을 기준으로 시작한다

- 날짜: 2026-04-30
- 상태: Accepted
- 배경:
  - TI SDK/Yocto 계열 빌드 환경은 Ubuntu LTS 기준으로 구성하는 것이 일반적이다.
  - Ubuntu 22.04 WSL 환경 준비가 완료되었다.
- 결정:
  - 초기 빌드/학습 환경은 Ubuntu 22.04 WSL 기준으로 문서화한다.
- 영향:
  - 이후 명령어와 패키지 설치 절차는 Ubuntu 22.04 기준으로 작성한다.
- 재검토 조건:
  - 특정 TI SDK 버전이 다른 Ubuntu 버전을 요구하거나 WSL 제한에 걸릴 때

## D-003. TI SDK source workspace와 patch 기반 repo 운영 정책을 사용한다

- 날짜: 2026-05-13
- 상태: Accepted
- 배경:
  - TI Processor SDK는 U-Boot, Linux kernel, TF-A, OP-TEE, toolchain, rootfs, prebuilt image 등을 포함하는 큰 BSP workspace이다.
  - U-Boot/Linux 전체 source tree를 `TI_BringUP` 원격 repo에 동기화하면 repo가 커지고, TI BSP 업데이트 추적이 어려워진다.
  - 커스텀 보드 BSP 작업은 보통 전체 source tree 수정이 아니라 Device Tree, defconfig, board 설정, rootfs overlay, patch 중심으로 관리하는 것이 적합하다.
  - AI Agent 기반 분석과 빌드 편의성을 위해 로컬에는 source tree가 필요하다.
- 결정:
  - TI Processor SDK 원본은 `~/ti/am64x/ti-processor-sdk-linux-am64xx-evm-12.00.00.07.04` 아래에 reference/build dependency로 유지한다.
  - `TI_BringUP` repo에는 U-Boot/Linux 전체 source tree를 원격 동기화하지 않는다.
  - 로컬 `TI_BringUP/workspace/` 아래에 SDK source tree를 복사 또는 checkout하여 분석/수정/빌드 작업에 사용한다.
  - `workspace/`는 Git 관리 대상에서 제외한다.
  - 의미 있는 source 변경은 workspace 내부 git commit으로 정리한 뒤 patch로 export하여 `bsp/*/patches/`에 저장한다.
  - 다른 머신에서는 동일 TI SDK와 `TI_BringUP` repo의 prepare/build script를 이용해 workspace를 재현한다.
- 영향:
  - `TI_BringUP` repo는 source mirror가 아니라 BSP 변경사항, 문서, manifest, script, patch, board note 저장소로 운영한다.
  - 장기 보관 대상은 source tree 전체가 아니라 patch, config fragment, DTS 후보, rootfs overlay, build/install script, manifest가 된다.
  - local AI Agent는 `workspace/`의 source tree를 참조해 코드 분석과 빌드를 수행할 수 있지만, 해당 source tree는 원격 repo에 push하지 않는다.
  - TI SDK 버전이 변경되면 새 SDK source tree에 기존 patch set을 재적용하여 호환성을 검증한다.
- 재검토 조건:
  - 실제 커스텀 보드 개발 과정에서 U-Boot/Linux core code 수정이 많아져 patch 관리만으로 추적이 어려워질 때
  - 여러 개발 머신 또는 협업자가 동일 source tree branch를 공유해야 할 필요가 생길 때
  - Yocto 기반 제품 이미지 관리 단계로 넘어가 `meta-nstel` 또는 custom BSP layer 중심 운영이 필요해질 때
  - TI SDK major version 변경으로 기존 patch set 재적용 비용이 커질 때

## D-004. 현재 SK-AM64B 파이프라인 BASE는 U-Boot env 기반 SD boot flow로 유지한다

- 날짜: 2026-05-14
- 상태: Accepted
- 배경:
  - self-built U-Boot boot logs show the current successful path loading kernel and DTB directly before `booti`.
  - U-Boot `printenv` confirms the active policy is driven by `bootcmd`, `bootcmd_ti_mmc`, `bootpart=1:2`, `bootdir=/boot`, and `fdtfile=ti/k3-am642-sk.dtb`.
  - The currently running board state matches this path and does not depend on an active `extlinux.conf` baseline.
- 결정:
  - The first deploy pipeline will preserve the current U-Boot environment-driven SD boot flow as the project BASE.
  - Kernel deploy will target `/boot/Image`.
  - DTB deploy will target `/boot/dtb/ti/k3-am642-sk.dtb`.
  - Bootloader deploy will target the FAT boot partition artifacts without rewriting boot policy.
- 영향:
  - Bootloader, kernel, DTB-only, and rootfs loops will be implemented independently against the current working layout.
  - Future boot-policy changes must be documented explicitly as deltas from this baseline.
  - extlinux/test-golden slot management is deferred until there is a concrete operational need.
- 재검토 조건:
  - repeated testing requires slot-based rollback
  - direct U-Boot env boot becomes difficult to manage safely
  - extlinux or EFI menu control becomes operationally necessary

## D-005. 반복 SD bring-up 작업의 recovery anchor로 OSPI known-good bootloader를 유지한다

- 날짜: 2026-05-14
- 상태: Accepted
- 배경:
  - SK-AM64B에서 OSPI Flash에 bootloader를 기록하고 boot mode switch를 바꾸어 OSPI 기반 U-Boot 부팅을 검증한 기록이 이미 있다.
  - SD bootloader 실험은 `tiboot3.bin`, `tispl.bin`, `u-boot.img` overwrite를 포함하므로 실패 시 SD 자체로는 복구가 어려울 수 있다.
  - kernel/DTB/rootfs 문제와 달리 bootloader 문제는 SSH 복구 진입점 자체를 잃을 수 있다.
- 결정:
  - 반복 bring-up 작업에서는 OSPI에 known-good bootloader를 유지하는 전략을 사용한다.
  - 초기 안정화 단계에서는 TI prebuilt bootloader 또는 이미 충분히 검증된 조합을 OSPI golden으로 사용한다.
  - SD는 반복 실험 대상 영역으로 운영한다.
  - SD bootloader 문제 발생 시 boot mode switch를 OSPI 쪽으로 바꾸어 복구 경로를 확보한다.
- 영향:
  - bootloader deploy 전략에는 OSPI write/use/recovery 절차가 포함되어야 한다.
  - deploy 전 체크리스트에 OSPI golden 존재 여부와 boot mode switch 상태 확인이 포함된다.
  - OSPI를 Linux 전체 대체 경로가 아니라 U-Boot까지의 recovery anchor로 다룬다.
- 재검토 조건:
  - OSPI에도 self-built golden을 승격할 정도로 충분한 검증 체계가 마련될 때
  - SD/OSPI를 함께 포함한 A/B slot 전략이 필요해질 때
  - 보드 운용 방식이 바뀌어 OSPI recovery 의존도를 낮출 수 있을 때

## D-006. SK-AM64B R5F remoteproc 이슈는 module sync + rpmsg userspace startup ordering 이슈로 분류한다

- 날짜: 2026-05-15
- 상태: Accepted
- 배경:
  - SK-AM64B에서 R5F 동작 여부를 확인하는 과정에서 `modprobe ti_k3_r5_remoteproc` 실패, `/sys/class/remoteproc/` empty 관측, `remoteproc ... releasing ...` 로그, `rpmsg_json.service` 실패가 함께 보였다.
  - 초기에는 R5F remoteproc bring-up 자체 실패로 해석될 수 있었다.
  - 이후 current kernel release 기준 module tree를 배포한 뒤, clean reboot 재검증과 live board 확인을 통해 remoteproc registration, firmware boot, RPMsg host online, `state=running` 상태가 모두 정상임을 확인했다.
- 결정:
  - 이 이슈는 “R5F bring-up 실패”로 분류하지 않는다.
  - 1차 문제는 kernel/modules sync mismatch로 본다.
  - 잔여 문제는 `rpmsg_json.service` 가 remoteproc/rpmsg 준비 이전에 시작되는 userspace startup ordering race로 본다.
  - 장기 히스토리 제목은 `SK-AM64B R5F remoteproc module sync 및 rpmsg startup race 해결`로 유지한다.
- 영향:
  - 향후 유사 이슈에서는 먼저 `uname -r` 와 `/lib/modules/<release>` 일치 여부를 확인한다.
  - remoteproc 문제로 보이면 clean reboot 후 `/sys/class/remoteproc/*/state` 와 boot log를 우선 확인한다.
  - RPMsg userspace 실패는 remoteproc bring-up 실패와 분리하여 판단한다.
- 관련 문서:
  - `docs/research/2026-05-15_am64x_remoteproc_empty_sysfs_after_module_load.md`
  - `docs/boards/SK-AM64B/issues/2026-05-15_r5f-remoteproc-module-sync-and-rpmsg-race.md`
  - `docs/bringup-logs/2026-05-15_sk-am64b_r5f_remoteproc_rpmsg_resolution.md`
  - `logs/runtime/2026-05-15_sk-am64b_r5f_remoteproc_verification_log.md`
- 재검토 조건:
  - clean reboot 기준으로 remoteproc `state=running` 이 더 이상 재현되지 않을 때
  - 다른 보드 또는 다른 boot chain에서 동일 현상이 다른 원인으로 반복될 때

## D-007. SK-AM64B R5F H/W Control Phase 1은 전용 project docs를 canonical로 사용한다

- 날짜: 2026-05-20
- 상태: Accepted
- 배경:
  - SK-AM64B R5F H/W Control Phase 1 관련 계획, 적용 절차, 프로토콜, 실측 절차, 완료 상태가 project docs와 root `docs/` 아래에 중복 기록되기 시작했다.
  - root `docs/boards/SK-AM64B/r5f-hw-control/` 아래 문서는 project docs와 주제와 내용이 강하게 겹쳤고, 일부는 connector pin mapping을 project docs보다 더 단정적으로 서술했다.
- 결정:
  - Phase 1의 canonical 문서는 `projects/am64x-r5f-hw-control-lab/docs/` 아래에 둔다.
  - root `docs/` 아래에는 repo-wide decision, research, setup, bring-up history만 남긴다.
  - root `docs`에 임시로 추가된 Phase 1 중복 문서는 canonical 문서에 흡수하거나 삭제한다.
- 영향:
  - project scope 내용은 project docs에서만 유지한다.
  - repo-level `DECISION_LOG`에는 구조와 운영 원칙만 남기고, 상세 절차/배선/검증 체크리스트는 project docs로 위임한다.
  - `MCU_GPIO0_8` connector-level mapping은 실제 실측 전까지 project docs 기준으로 미검증으로 유지한다.
- 관련 문서:
  - `projects/am64x-r5f-hw-control-lab/README.md`
  - `projects/am64x-r5f-hw-control-lab/docs/plan.md`
  - `projects/am64x-r5f-hw-control-lab/docs/board-apply.md`
  - `projects/am64x-r5f-hw-control-lab/docs/protocol.md`
  - `projects/am64x-r5f-hw-control-lab/docs/test-procedure.md`
  - `projects/am64x-r5f-hw-control-lab/docs/completion.md`
  - `projects/am64x-r5f-hw-control-lab/docs/issues.md`
- 재검토 조건:
  - 동일 project에 대해 repo-wide docs가 별도 canonical 위치를 가질 필요가 생길 때
  - Phase 1이 제품 문서/board 공통 문서로 승격되어 project 범위를 넘어설 때

## D-008. UART MCP는 단일 server와 target 파라미터로 보드를 구분한다

- 날짜: 2026-06-18
- 상태: Accepted
- 배경:
  - 여러 보드의 `uartd`를 target 기반으로 제어해야 한다.
  - target별 MCP alias를 추가하면 같은 tool 세트가 중복 노출되어 tool inventory와 토큰 사용량이 불필요하게 증가한다.
  - 이미 `uartctl.py`와 `uart-mcp-server.py`는 `sk`, `custom` target profile을 공통으로 해석할 수 있다.
- 결정:
  - UART MCP는 generic `uart` server 하나만 유지한다.
  - 실제 보드 구분은 MCP tool argument의 `target` 필드로 수행한다.
  - 기본 target은 `sk`로 둔다.
  - 현재 기준 target endpoint는 `custom=192.168.0.170:17001`, `tmds=192.168.0.170:17002`, `sk=192.168.0.170:17003`이다.
- 영향:
  - MCP tool 수를 늘리지 않고 `sk`/`custom` endpoint를 선택할 수 있다.
  - 새 세션에서는 요청 문맥에 따라 `target=sk` 또는 `target=custom`을 명시해 호출한다.
  - 커스텀 보드 원격 daemon의 `runtime_log`는 local filesystem 기준 canonical 증적으로 가정하지 않는다.
- 관련 문서:
  - `docs/common/UART_DAEMON_AGENT_WORKFLOW.md`
  - `docs/bringup-logs/2026-06-18_uart-mcp-target-routing-validation.md`
  - `test_todo.md`
- 재검토 조건:
  - tool inventory 증가 없이 target 고정 convenience를 제공할 다른 MCP 메커니즘이 필요해질 때
  - 원격 custom board runtime log를 이 host에서 안정적으로 참조/동기화하는 구조가 생길 때
