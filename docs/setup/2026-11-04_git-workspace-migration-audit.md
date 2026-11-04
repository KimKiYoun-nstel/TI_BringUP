# Git 상태 및 작업 연속성 기준 마이그레이션 선별

> 후속 사용자 확정: UART 관련 변경은 commit/push에서 제외한다. workspace는 대상에서
> 원본 설치 패키지와 Git/공식 patch로 재구성한다. TSN raw artifact/log 및 `.agents/`는
> 전송 보류, 회로도 PDF/DB 및 보드 image는 동기화한다. 아래의 조사 당시 권장 보존 목록과
> 구분하며, 실제 실행 기준은 [workspace 재구성 가이드](2026-11-04_target-workspace-reconstruction.md)를 따른다.

## 1. 목적과 결론

새 장비 `prodigyrcn@192.168.0.107`에서 기존 bring-up 작업을 이어가기 위해, 상위 Git 변경과 로컬 전용 자산을 먼저 분류했다. 이 문서는 설치 기록과 별개인 **이전 대상 선별 결과**다.

1. 상위 repo는 **push만 빠진 상태가 아니다**. 로컬 `main`과 실제 GitHub `main`이 동일하며, P3 Qbu 작업 등이 아직 commit되지 않았다.
2. 미커밋 파일 대부분은 의미 있는 작업 결과다. 단, Python cache는 제외 대상이고 UART 변경에는 기존 인터페이스 회귀가 있어 그대로 일괄 commit하면 안 된다.
3. `workspace/`는 상위 Git 관리 밖인 소스 작업 공간이다. 공식 patch로 재구성 가능한 소스와, 아직 별도 보존해야 할 commit/진단 diff/stash를 구분한다.
4. 작업 연속성에는 source뿐 아니라 Git 제외 원시 증적, golden image, 회로도 입력, 로컬 가이드가 필요하다.

분석 중 기존 source와 미커밋 파일은 변경하지 않았다. commit/push, 파일 삭제, 대상 장비 추가 변경도 수행하지 않았다.

## 2. 상위 repo 동기화 상태

확인 시점은 이 감사 문서를 추가하기 전이다.

| 항목 | 확인 결과 |
|---|---|
| branch | `main` |
| 로컬 HEAD / `origin/main` / 실제 원격 main | `5fecbf52a13fc231071c85975a0bdece75ddc73c` |
| 마지막 commit | 2026-07-28 18:57:39 +0900, `projects: finalize P2 Qbv window validation` |
| 다른 로컬 branch | `phase2-tsn-c4-rproc-scaffold`도 실제 원격과 같은 `be3ba6794c8ac87fc50ee370ca2b84b6a858daf2` |
| staged 변경 / 상위 repo stash | 없음 / 없음 |
| tracked 미커밋 변경 | 13개, 139 insertions / 81 deletions |
| untracked 파일 | 38개: P3 29개, 기타 문서 3개, Python cache 6개 |

원격 값은 `git ls-remote origin refs/heads/main` 및 해당 다른 branch로 직접 확인했다. **왜 commit을 생략했는지는 Git 이력만으로 확정할 수 없다.** 확인 가능한 사실은 7월 28일 P2 마감 이후 7~8월 P3 실행 도구/결과와 10월 종합 정리가 working tree에 남았다는 것이다.

## 3. 미커밋 변경의 작업별 판정

| 작업 묶음 | 파일 범위 | 판단 및 동기화 전 조치 |
|---|---|---|
| P3 Qbu 정량 시험 | `projects/am64x-tsn-quant-validation/config/p3-*.json` 14개, `docs/p3-*.md` 12개, `tools/p3_qbu_*` 3개, 기존 README/measurement-plan/workspace-sdk-cross-check 수정 | **보존 및 Git 동기화 대상.** 실행 도구·matrix·실측 결과가 연결된 후속 작업이다. README와 일부 계획 문서의 상태/배선 표현은 결과에 맞춰 정리 필요 |
| Qbv pair2 replay | `projects/tsn_qbv/board/prepare_endpoint_target.sh`, `docs/2026-07-28_pair2-hardware-taprio-replay.md` | **보존 및 Git 동기화 대상.** skb priority 3/2와 wire PCP 7/6을 분리하는 실제 classifier 수정 및 재현 결과 |
| UART CLI | `tools/uart/uartctl.py` | **의미 있는 변경이지만 통합 보정 후 동기화.** Windows Ctrl+C를 UART ETX로 전달하는 개선과 `--target`/`--targets-file` 제거 회귀가 혼재 |
| 실험실 접속 정보 | 두 board `profile.yaml`, `tools/uart/targets.json`, UART README 및 공통 문서 | `192.168.0.170 → .55`, TMDS 관리 IP `.220 → .59`의 일관된 갱신. **이전 시 확인할 운영 정보.** 현재 실제 endpoint 유효성 확인 후 동기화 |
| TSN 종합 결과 | `docs/outputs/am64x-tsn-validation-summary.md`, outputs README, TASK_BOARD | **보존 및 Git 동기화 대상.** 10월 27일 기존 문서/로컬 artifact를 종합한 결과이며 신규 실보드 시험은 아님 |
| 장비 이전 기록 | `docs/setup/2026-11-04_ubuntu24-host-migration.md`, root README 링크 | **보존 및 Git 동기화 대상.** 이번 설치 세션에서 추가한 파일 |
| Python cache | `projects/am64x-tsn-quant-validation/tools/__pycache__/*.pyc` 6개 | **Git/이전 대상에서 제외.** 실행 시 재생성 가능. 이번에는 삭제하거나 ignore 규칙을 수정하지 않음 |

### 그대로 commit하기 전 해결할 불일치

- 현재 `uartctl.py`에서 `--target sk status`는 인자 파싱 단계에서 실패한다. 기존 `projects/am64x-tsn-quant-validation/tools/p2_qbv_multiclass_pilot.py:43` 및 `projects/am64x-tsn-validation-automation/board/tsn_validate.py:44`는 이 인터페이스를 사용한다. 기본 접속도 target profile 대신 로컬 Unix socket으로 바뀌었다.
- Windows Ctrl+C 개선은 별도로 보존하되 기존 `uart_endpoint` 기반 target 선택과 함께 동작하도록 통합해야 한다. Windows 실환경 동작은 이번에 검증하지 않았다.
- P3 도구는 현재 `--tcp`와 `192.168.0.55:17002/17003`을 직접 사용하므로 위 `--target` 회귀와는 호출 방식이 다르다. 다만 새 장비에서 UART endpoint 설정을 한 곳으로 맞출 필요가 있다.
- P3 README는 아직 `준비 완료 / matrix 대기`로 표시되지만 실제 결과는 8월 11일까지 있다. README의 “P2와 동일한 SK eth1 배선”과 cross-check의 historical SK eth0 예시도 현재 P3 `TMDS eth1 → SK eth1` 결과와 구분해 고쳐야 한다.
- P3 status 문서의 마지막 “다음 diagnostic run”보다 최신인 `artifacts/p3-qbu-operational-20260811-105003-kst`가 존재한다. status/README의 canonical 상태를 이 결과까지 맞춘 후 동기화하는 것이 좋다.

### 의미 있는 실측 결과라는 근거

- `p3-qbu-combined-endurance-result-2026-08-04.md`: 독립 reboot 후 첫 300초 on-run에서 preemptible loss 10, acceptance 실패. 실패도 보존해야 할 시험 결과다.
- `p3-qbu-loss-location-isolation-result-2026-08-04.md`: UDP RX buffer와 SMD error를 구분한 A/B 및 fragment/pacing 비교.
- 최신 `p3-qbu-operational-20260811-105003-kst/campaign-status.json`: `completed`, 6 runs, `valid: true`.
- 같은 campaign summary: control 1회 + on 300초 × 5회, on `active: 5`, 양 flow loss 0, assembly/SMD error 0. **production profile 확정과는 별개**이며 이전 reboot/loss 실패를 대체하지 않는다.

## 4. workspace별 실제 상태와 이전 방법

아래 상태는 원본 장비의 read-only Git 확인 결과다. 진단 트리의 dirty 상태를 발견했으므로 수정·정리 작업은 수행하지 않았다.

| workspace | 현재 상태 | 공식 자산 대조 및 이전 판단 |
|---|---|---|
| `ti-linux-kernel-sdk12` | clean, `phase2-tsn-pktgen`, HEAD `c214492085504176b9c252a7175e4e60b4b442af` | SDK baseline과 동일, 추가 source delta 없음. **정확한 baseline으로 재구성**. branch 이름만으로 pktgen source 변경이 있다고 보면 안 됨. 실행 Image/빌드 설정은 별도 확인 |
| `ti-u-boot-sdk12` | clean, `base-sd-watchdog`, HEAD `ecaf8c660efb0dfbf204e8443025a83d115b03b1` | baseline 대비 bootdelay=5 한 commit. `bsp/u-boot/patches/0002-...`와 stable patch-id 일치. **baseline + 선택 patch로 재구성 가능** |
| `ti-u-boot-sdk12-sk-am64b-local-fullchain` | clean, `ti-u-boot-2026.01`, HEAD `30df77692826088c106227ed93579b7966f6ddc7` | 위 U-Boot repo와 **linked worktree**. RM ownership commit `9cddf3cf1a0`은 공식 `0001-...`와 patch-id 일치. 그러나 bootdelay=10은 현재 공식 bootdelay=5 patch와 다름. **local-fullchain branch 이력 보존 및 목적별 재구성 필요** |
| `mcu_plus_sdk_am64x_12_00_00_27` | clean, `phase2-tsn-c-case`, HEAD `723147ec9eb1143c4100c6f1da4d153455c3e752` | baseline 이후 두 commit `6f7e325b`, `723147ec`가 `projects/tsn_c_case/patches/0001`, `0002`와 각각 patch-id 일치. **공식 project patch로 재구성 가능** |
| `trusted-firmware-a-2.14+git` | clean, HEAD `44fcd9c2d62460a780a5e76f6e65202c37d8dbb7` | manifest의 SDK 초기 `76500cea...`보다 899 reachable commits 뒤. **현재 정확한 commit/object를 별도 보존**해야 local-fullchain 입력 연속성 유지 가능 |
| `optee-os-4.9.0+git` | clean, HEAD `60706ecef7619a01c5f5da20ea12a832699a1440` | manifest의 SDK 초기 `f2a7ad06...`보다 165 reachable commits 뒤. **현재 정확한 commit/object 별도 보존** |
| `trusted-firmware-a-2.14+git-bl31diag` | 위 TF-A HEAD + `bl31/bl31_main.c` 미커밋 52줄 추가 + stash 1개 | 현재 diff와 stash가 서로 다른 파일/계측을 포함함. **둘 다 별도 보존**. build에 자동 적용할 자산으로 보지 않음 |
| `optee-os-4.9.0+git-bl32diag` | 위 OP-TEE HEAD + `core/arch/arm/plat-k3/main.c` 미커밋 변경 + stash 1개 | BL32 계측과 secure-info/HUK bypass 진단 변경. **diff와 stash 별도 보존**, stock/canonical source와 구분 |

### 공식 자산과 로컬 이력의 주의점

- U-Boot `series`는 현재 `0002`만 선택한다. RM `0001` patch가 존재한다고 해서 모든 목적의 build에 자동 적용되는 것은 아니다.
- `0002` patch 메일 header의 From SHA는 `30df776...`지만 본문은 bootdelay=5다. 현재 local-fullchain commit `30df776...`의 본문은 bootdelay=10이다. **header SHA만으로 같다고 판단하지 않았으며 patch-id로 확인했다.**
- MCU+ local bare seed `~/ti/local_git_repo/mcu_plus_sdk_am64x_12_00_00_27.git`에는 baseline `44bd053362cf25ca0fdddef81c33b024f083eead`와 C Case branch가 모두 있다. 이는 GitHub가 아니라 원본 장비에만 있는 local remote다. patch 재현에는 필수가 아니지만 기존 Git 이력/branch 연속성을 위해 **bundle 또는 bare repo 보존을 권장**한다. 디스크 사용량은 약 3.9MB다.
- MCU+의 C Case 두 patch와 `bsp/mcu-plus/patches/series`의 non-C-Case patch는 목적이 다르다. 전부 일괄 적용하지 않고 프로젝트별로 선택한다. 근거는 `logs/provenance/mcu-plus/2026-07-07_mcu-plus-local-git-seed-transition.md`다.
- TF-A/OP-TEE origin은 원본 장비의 `/home/nstel/ti/am64x/...` 로컬 SDK 경로다. 새 장비에서는 원격 경로도 대응해야 한다. `master...origin/master`라는 표시가 GitHub 보존을 뜻하지 않는다.
- stash tip: TF-A `00454ace54ee5a73cb219355bac4653ddf0d9e52`, OP-TEE `3e3e51c46f13174622098a7f7ce22b10303a6d83`. 각 stash는 현재 working diff와 다르며 소스 폴더 재생성만으로 복구되지 않는다.

### 소스 이력 보존 방식

후속 실행에서는 필요한 source repo를 `git bundle --all`로 보존하고, uncommitted diff는 `git diff HEAD --binary`, stash는 `git stash show -p --binary` 및 ref 기록으로 따로 보존한다. bundle 생성 후 `git bundle verify`를 수행한다. 현재 진단 트리는 각각 stash 1개이며, 일반적으로 `--all`이 모든 과거 reflog/stash entry를 보존한다고 가정하면 안 된다.

U-Boot linked worktree 디렉터리만 복사하면 `.git`의 원본 절대 경로 참조가 남는다. 원본 repo 이력을 복원한 뒤 새 경로에서 `git worktree add`로 구성한다. 이번에는 bundle/export 또는 소스 이전을 실행하지 않았다.

## 5. Git 밖에서 별도 이전할 정보

용량은 원본 장비 `du -sh` 기준이며 archive 크기가 아니다.

| 우선순위 | 경로/자산 | 규모 | 선정 이유와 방법 |
|---|---|---:|---|
| 필수 | `projects/am64x-tsn-quant-validation/artifacts/` | 264MB | P1/P2/P3 원시 증적. 최신/실패/partial campaign을 구분해 그대로 별도 archive. Git에는 raw 전체를 올리지 않음 |
| 필수 | `projects/am64x-tsn-validation-automation/logs/20260714-*/` | logs 전체 약 2.2MB | 기능 regression의 Git 제외 raw 결과. `.gitkeep`만 clone되는 상태 |
| 필수 | `.agents/` | 676KB | README가 참조하는 정량 검증 가이드 및 bring-up handoff. Git 제외지만 cache가 아님. 과거 시점 문서는 현재 canonical 결론과 구분 |
| 필수 | `tools/custom_board_dts_workflow/.../cpu_brd_v03_pba_260511/inputs/schematic/CPU_Brd_V03_PBA_260511.pdf` | 별도 파일 | Git 제외 회로도 원본 입력. netlist/생성 DTS만으로 대체되지 않음 |
| 필수 | `tftp/Image.golden`, `k3-am642-sk.dtb.golden`, `tftp/am64x-sbl-ospi-local-fullchain-canonical/` | tftp 전체 46MB | 복구용/채택 binary. hash와 provenance를 함께 보존. 설치 패키지/patch만으로 동일 binary라고 가정하지 않음 |
| 필수 | `out/sk-am64b-sbl-ospi-linux-local-fullchain/` | 3.5MB | 채택 image와 source/staged hash를 담은 build manifest. tftp와 중복 파일도 manifest 연결을 유지 |
| 선별 보존 | `out/`의 나머지 image, `.config`, manifest, diagnostic 출력 | out 전체 4.9GB | 빌드 캐시와 구분해 기존 실행 Image/DTB/modules/firmware 및 진단 결과를 보존. kernel/bootloader provenance가 불명확한 binary는 재현 검증 완료 전 삭제하지 않음 |
| 선별 보존 | `projects/tsn_qbv/logs/` 등 나머지 project log | Qbv logs 9.7MB | 일부는 tracked, 일부 생성 파일은 ignored. **project logs 전부가 Git 제외라는 뜻은 아님**. tracked 여부와 문서 참조를 확인해 차집합 archive |
| 선별 보존 | `firmware/`, `tmp/` | 36KB / 68KB | 로컬 메모와 과거 capture가 포함됨. 이름만 보고 cache로 삭제하지 말고 필요한 증적 보존. `tmp/*known_hosts`는 새 장비 설정과 구분 |
| 재생성/경로 대응 | `tools/env/*.env` | 소량 | 현재 두 파일은 `.env.example`과 내용 일치. 새 `$HOME` 기반으로 재생성 가능 |
| 경로 대응 | DTS `config/paths.local.yaml` | 소량 | `/home/nstel/...` 절대 경로를 새 사용자 경로로 대응. 내용은 참고 보존하되 그대로 사용하지 않음 |
| 별도 점검 | `.opencode/`, 사용자별 도구/인증 설정 | .opencode 전체 69MB | 필요한 사용자 설정/plugin 의존성만 선별. `node_modules`와 cache는 재설치. 이번 감사에서 설정 상세·인증정보는 분석하지 않음 |
| 증적 snapshot | `logs/runtime_log` | 별도 파일 | 현재 filesystem상 일반 파일. 기존 UART 동기화 구조와 별개로 snapshot을 보존하고 새 연결 경로를 확인 |

원본 `~/ti/TI_Bringup_Repo_Setup_Agent_Guide.md`도 Git clone 밖의 설정 가이드이므로 로컬 가이드 archive에 포함할 수 있다.

### 명확한 재생성 대상

- `__pycache__`, `*.pyc`, `.opencode/node_modules`.
- baseline 및 공식 patch로 구성 가능한 source checkout 자체.
- 성공 재빌드와 canonical hash/provenance 검증 후 불필요해진 중간 object/cache.

이 목록은 삭제 지시가 아니다. 특히 아직 source provenance/재현이 확인되지 않은 `out/` 전체를 단순 cache로 취급하지 않는다.

## 6. 대상 장비의 두 source 폴더 해석

앞선 설치 준비 과정에서 `tools/prepare/create-workspace.sh`가 U-Boot/Linux 두 폴더를 새 SDK source로부터 복사했다. 이들은 **원본 장비의 작업 workspace를 이식한 결과가 아니다**. 기존 두 폴더는 source 재구성 전의 초기 입력으로 취급한다.

Linux SDK 패키지의 추적 파일 변경 및 U-Boot `oe-gitpkgv_*`도 함께 복사되어 있다. 이를 먼저 지우는 것보다, 이번 선별을 기준으로 프로젝트별 baseline/patch/로컬 이력을 정한 뒤 필요한 source를 재구성하는 순서가 맞다. 대상 폴더를 이번 감사에서 수정하지 않았다.

## 7. 권장 마이그레이션 순서

1. **상위 Git 정리**: P3 결과/도구, Qbv replay, UART 통합 보정, TSN 종합 문서, 이전 기록을 작업 묶음별로 검토한다. cache를 제외하고 문서 불일치를 보정한 뒤 commit/push한다.
2. **로컬 전용 정보 보존**: raw artifacts, 가이드/PDF, golden binary+manifest, TF-A/OP-TEE commit/diff/stash, U-Boot fullchain branch, MCU+ seed 이력을 archive/bundle과 hash 목록으로 만든다.
3. **대상 상위 repo 동기화**: 새 commit을 pull하고 별도 archive를 원래의 상대 경로에 복원한다.
4. **프로젝트별 source 재구성**: kernel baseline, 기본 U-Boot, fullchain U-Boot worktree, MCU+ C Case 또는 SBL 목적별 patch, TF-A/OP-TEE 정확한 commit을 선택한다. diagnostic diff는 별도 topic에만 복원한다.
5. **호스트 경로 대응**: `.env`, DTS local path, local Git remote, UART/board profile, TFTP/NFS 경로를 조정한다.
6. **작업 연속성 검증**: 기존 raw 결과의 offline 재집계 → source 상태/선택 patch 확인 → 필요한 build → 연결된 보드의 boot/runtime identity 확인 순서로 진행한다.

따라서 “로컬 workspace 전체 복사”와 “새 SDK baseline만 사용” 중 하나를 일괄 선택할 필요가 없다. **공식 자산으로 재생성할 것은 재생성하고, 로컬에만 남은 정보는 별도로 보존**하는 혼합 방식이 현재 운영 정책에 맞다.

## 8. 이번 감사의 확인 범위

- Git status/diff/log/reflog/stash/branch/worktree 및 실제 원격 SHA 확인.
- MCU+ 두 commit, 기본 U-Boot bootdelay=5 및 fullchain RM delta의 stable patch-id 대조.
- P3 최신 campaign status/summary와 결과 문서 대조.
- `python3 -m unittest discover -s tests/tools/uart -p test_uartctl.py -v`: 기존 parser test 1개 통과. 단, 이 test는 `--target` 회귀를 검사하지 않음.
- `python3 -B tools/uart/uartctl.py --target sk status`: 보드 접속 전 인자 파싱 실패 확인.
- Qbv/P3 shell script `bash -n`, P3 Python CLI `--help`, P3 matrix 14개 JSON 구문 검증 통과.
- 실보드 UART 명령, traffic 재시험 및 전체 빌드는 수행하지 않음. 유효 원시 증적의 전 packet 재분석도 이번 범위 밖이다.

관련 설치 결과: [Ubuntu 24.04 개발 호스트 이전 준비 기록](2026-11-04_ubuntu24-host-migration.md).
