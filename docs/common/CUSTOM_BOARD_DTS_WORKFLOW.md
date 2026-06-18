# 커스텀 보드 DTS 워크플로우 연동 가이드

## 목적

이 문서는 root repo에서 커스텀 보드용 Linux/U-Boot DTS를 재구성하고, 그 결과를 실제 build 입력으로 연결할 때 따라야 할 기준 흐름을 정의한다.

핵심은 다음 세 줄이다.

- SK-AM64B reference만으로 커스텀 보드 DTS를 가정하지 않는다.
- 커스텀 보드의 기준 정보는 `tools/custom_board_dts_workflow` 아래의 board project 입력과 산출물이다.
- 실제 build 입력 DTS는 root repo의 `bsp/*/dts/custom-board/.../sets/<purpose>/` 아래에서 별도 관리한다.

## 왜 별도 워크플로우가 필요한가

SK-AM64B나 TMDS64EVM은 TI SDK 안에 reference DTS, build target, 공개 board 정보가 이미 많이 포함되어 있다. 반면 커스텀 보드는 다음 정보가 root repo 안에서 1차 근거가 된다.

1. `.NET` netlist
2. `inputs/schematic/hardware_db/`
3. SysConfig pinmux DB
4. `docs/board_dts_decisions.yaml`

즉 커스텀 보드 작업에서는 TI SDK reference DTS가 출발점이 아니라 integration precedent에 가깝다.

## 기준 경로

워크플로우 루트:

- `tools/custom_board_dts_workflow/`

현재 보드 project:

- `tools/custom_board_dts_workflow/platforms/am64x/projects/cpu_brd_v03_pba_260511/`

현재 보드 project에서 먼저 볼 경로:

1. `inputs/schematic/hardware_db/`
2. `docs/board_dts_decisions.yaml`
3. `generated/linux/final/`
4. `generated/uboot_spl/final/`
5. `delivery/linux/`
6. `delivery/uboot_spl/`

## 입력과 산출물의 역할

### 입력층

- `.NET`: board wiring fact
- `hardware_db`: PDF 회로도에서 추출한 reusable schematic semantic DB
- SysConfig DB: SoC pinmux 사실 검증 입력
- `board_dts_decisions.yaml`: 사람이 확정한 보드 정책/판단 입력

### 산출물층

- `generated/linux/base/`, `generated/uboot_spl/base/`: helper가 조합한 시작점
- `generated/*/final/`: workflow가 관리하는 최종 산출물
- `delivery/`: handoff와 재편집 전달에 적합한 DTS 세트
- `reports/`: 검토 증적

### root-managed build 입력층

- `bsp/linux/dts/custom-board/<board>/sets/<purpose>/`
- `bsp/u-boot/dts/custom-board/<board>/sets/<purpose>/`

이 계층은 workflow 작업 구역과 다르다. 여기에는 실제 target에 의미 있는 정책이 반영되어, build 입력으로 채택된 DTS 세트만 둔다. 시험용 scratch DTS나 review 중간물은 두지 않는다.

## root repo에서의 권장 작업 흐름

### 1. DTS 재구성 요청

사용자가 커스텀 보드 DTS를 다시 만들거나 보강하라고 하면 다음 순서로 진행한다.

1. `tools/custom_board_dts_workflow/README.md`와 `docs/workflow_guide.md`를 읽는다.
2. board project의 `hardware_db`와 `board_dts_decisions.yaml`를 먼저 읽는다.
3. 필요하면 `python3 tools/custom_board_dts_workflow/scripts/run_stage1.py`를 실행한다.
4. `generated/*/final/`을 workflow 최종 산출물로 검토한다.
5. build에 실제 사용할 DTS는 root repo의 `bsp/*/dts/custom-board/.../sets/<purpose>/` 아래 세트로 승격할지 확인한다.

### 2. 실제 build 입력으로 연결

사용자가 custom board image build를 요청하면 다음을 먼저 확정한다.

1. Linux workflow 최종 산출물 기준 파일
2. U-Boot/SPL workflow 최종 산출물 기준 파일
3. root repo build DTS set 경로와 목적 이름
4. workspace source에 어떤 파일명으로 반영할지
5. 반영 후 어떤 build helper를 사용할지

현재 root repo helper:

- `tools/prepare/sync-custom-board-dts-set-to-workspace.sh`
- `tools/build/build-custom-board-linux.sh`
- `tools/build/build-custom-board-u-boot.sh`

현재 root repo build helper:

- `tools/build/build-kernel.sh`
- `tools/build/build-u-boot.sh`

이 일반 helper들은 현재 커스텀 보드 DTS 선택 정책을 내장하고 있지 않다. 따라서 custom board build는 root repo build DTS set를 workspace source of truth로 반영하는 전용 helper를 먼저 사용한다.

## workspace 반영 방식

### Linux

- workspace 경로: `workspace/ti-linux-kernel-sdk12/arch/arm64/boot/dts/ti/`
- top-level DTS는 board 이름 기준으로 별도 파일로 반영한다.
- `Makefile`에 해당 `.dtb` build entry를 추가해야 한다.

현재 `cpu_brd_v03_pba_260511 / bringup-default` 기준 workspace 파일명:

- `k3-am6412-cpu-brd-v03-pba.dts`
- `k3-am6412-custom-final-overrides.dtsi`
- `k3-am6412-custom-pinmux.facts.dtsi`

### U-Boot A53

- workspace 경로: `workspace/ti-u-boot-sdk12/dts/upstream/src/arm64/ti/`
- top-level DTS는 vendor path 기준 이름으로 반영한다.
- U-Boot는 matching `*-u-boot.dtsi`를 자동 include한다.

현재 기준 workspace 파일명:

- `dts/upstream/src/arm64/ti/k3-am6412-cpu-brd-v03-pba.dts`
- `arch/arm/dts/k3-am6412-cpu-brd-v03-pba-u-boot.dtsi`

### U-Boot R5 SPL

- workspace 경로: `workspace/ti-u-boot-sdk12/arch/arm/dts/`
- R5 SPL은 별도 top-level DTS가 필요하다.
- 이 R5 DTS는 A53 top-level DTS, DDR include chain, U-Boot quirks DTSI, `k3-am642-r5.dtsi`를 묶는 wrapper 역할을 한다.

현재 기준 workspace 파일명:

- `arch/arm/dts/k3-am6412-cpu-brd-v03-pba-r5.dts`

## U-Boot config 연결점

현재 TI AM64x U-Boot build에서 DT 선택 지점은 다음이다.

- A53: `CONFIG_DEFAULT_DEVICE_TREE`, `CONFIG_OF_LIST`
- R5 SPL: `CONFIG_DEFAULT_DEVICE_TREE`, `CONFIG_SPL_OF_LIST`

현재 root repo의 추천 override 자산:

- `bsp/u-boot/configs/custom-board/cpu_brd_v03_pba_260511/bringup-default-a53.config`
- `bsp/u-boot/configs/custom-board/cpu_brd_v03_pba_260511/bringup-default-r5.config`

현재 `cpu_brd_v03_pba_260511` runtime 확인값 기준 eMMC boot partition은 `boot0 = 4MiB`, `boot1 = 4MiB`다. 따라서 bringup-default는 EVM baseline `0x800 / 0x1800` 대신 small-layout candidate `0x400 / 0x1400`를 사용한다.

현재 build helper 동작:

- `build-custom-board-linux.sh`는 DTS set를 workspace kernel tree로 투영한 뒤 custom DTB를 빌드한다.
- `build-custom-board-u-boot.sh`는 DTS set를 workspace U-Boot tree로 투영하고, defconfig override와 current bringup-default용 binman DT filename patch를 적용해 빌드한다.

## 현재 남아 있는 U-Boot packaging 이슈

`CONFIG_DEFAULT_DEVICE_TREE`와 DTS source projection만으로는 충분하지 않을 수 있다.

이유:

- TI AM64x EVM target의 `k3-am64x-binman.dtsi`는 EVM/SK DT 이름을 명시적으로 나열한다.
- 따라서 custom board DTS로 source tree를 투영해도, 최종 `tiboot3.bin`/`tispl.bin` packaging에서 custom DT 이름이 자연스럽게 반영되는지 별도 검토가 필요하다.
- 현재 `build-custom-board-u-boot.sh`는 `bringup-default`에 한해 EVM/SK macro를 sibling `r5` output의 custom R5 DT와 `u-boot.dtb` 기준으로 덮어쓰는 실용적 patch를 적용한다.
- 즉 DTS source projection과 boot image packaging은 분리해서 보되, 현재는 bring-up 빌드를 위해 필요한 최소 packaging patch까지 포함한다.

## workflow final과 root-managed set의 관계

- `generated/*/final/`은 DTS 생성 workflow의 최종 산출물이다.
- root repo 입장에서 이 경로는 board별 reference이자 source material이다.
- 실제 build에 쓰는 DTS는 목적별로 root repo가 별도 소유해야 한다.

즉 현재 정책은 다음과 같다.

1. workflow에서 최종 DTS는 `final/`에 생성한다.
2. build 기준 DTS는 `final/`을 source로 삼는다.
3. 그러나 실제 build 입력은 `bsp/*/dts/custom-board/.../sets/<purpose>/`에 따로 관리한다.

## 목적별 DTS set 규칙

1. set 이름은 `bringup-default`, `ospi-priority`, `emmc-priority`처럼 목적을 드러내야 한다.
2. set 안에는 실제 build include chain이 끊기지 않도록 필요한 companion DTSI까지 함께 둔다.
3. set README에는 source workflow final 경로, 채택한 정책, 남은 TODO를 기록한다.
4. target 의미가 없는 시험용 DTS는 이 계층에 올리지 않는다.
5. workspace projection이 필요한 경우, target source tree에서 요구하는 top-level DTS 이름과 companion DTSI 이름을 별도로 명시한다.

현재 `cpu_brd_v03_pba_260511 / bringup-default`는 eMMC-first Linux boot 정책을 채택한다.

## 현재 boot source 해석

현재 `bringup-default` 기준 해석은 다음과 같다.

1. Boot ROM이 `tiboot3.bin`을 읽는 실제 물리 media는 board boot mode가 결정한다.
2. 다만 Linux handoff 기준 저장장치 정책은 eMMC-first다.
3. 현재 custom Linux/U-Boot set에서 `mmc0 -> sdhci0 -> eMMC`를 주 경로로 보고, `ospi0`는 fallback hardware candidate로 유지한다.
4. USB는 현재 `usb0 peripheral` 기준이므로 Linux boot source 기본 경로가 아니다.
5. 현재 eMMC raw bootloader layout candidate는 `tiboot3 @ 0x0`, `tispl @ 0x400`, `u-boot.img @ 0x1400`이다.

## 주의사항

1. `hardware_db`에 이미 반영된 `.NET` cross-check 결과를 PDF-only 해석으로 되돌리지 않는다.
2. DTS fact와 policy를 섞어서 설명하지 않는다.
3. build 전에 어떤 root-managed DTS set가 기준인지 명시하지 않은 채 workspace를 수정하지 않는다.
4. workspace 반영 후에는 provenance와 관련 문서를 함께 갱신한다.

## 다음 세션에서 바로 쓸 체크리스트

1. 이번 build에서 source workflow final로 어떤 파일을 기준으로 삼을지 확인
2. Linux root-managed DTS set 경로 확인
3. U-Boot root-managed DTS set 경로 확인
4. workspace kernel/U-Boot topic branch 확인
5. DTS 반영 대상 파일 경로 확인
6. `tools/build/build-kernel.sh`, `tools/build/build-u-boot.sh` 실행
7. 결과를 `logs/provenance/`와 보드 문서에 기록
