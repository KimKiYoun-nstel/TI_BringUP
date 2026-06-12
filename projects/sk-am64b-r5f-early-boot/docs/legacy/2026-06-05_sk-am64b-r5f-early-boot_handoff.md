# 2026-06-05 SK-AM64B R5F Early Boot Handoff

## 목적

이 문서는 다음 세션에서 SK-AM64B R5F early-boot 작업을 바로 이어가기 위한 handoff 문서다.

현재 작업은 `projects/sk-am64b-r5f-early-boot/` 를 main working surface 로 사용한다.

## 현재 canonical working surface

프로젝트 루트:

- `projects/sk-am64b-r5f-early-boot/`

핵심 문서:

- `projects/sk-am64b-r5f-early-boot/README.md`
- `projects/sk-am64b-r5f-early-boot/docs/plan.md`
- `projects/sk-am64b-r5f-early-boot/docs/gates.md`
- `projects/sk-am64b-r5f-early-boot/docs/phase2-execution-checklist.md`
- `projects/sk-am64b-r5f-early-boot/docs/phase2-uart-uniflash-runbook.md`
- `projects/sk-am64b-r5f-early-boot/docs/phase2-completion-boundary.md`

핵심 draft source:

- `projects/sk-am64b-r5f-early-boot/r5f/draft/main.c`
- `projects/sk-am64b-r5f-early-boot/r5f/draft/ipc_rpmsg_echo.c`
- `projects/sk-am64b-r5f-early-boot/r5f/draft/example.syscfg`
- `projects/sk-am64b-r5f-early-boot/r5f/draft/early_heartbeat_status.h`
- `projects/sk-am64b-r5f-early-boot/r5f/draft/ti-arm-clang/example.projectspec`

## 지금까지 한 일

### task-unit-1

- inventory / planning closeout 완료
- `Gate 1-A` passed

관련 문서:

- `projects/sk-am64b-r5f-early-boot/docs/task1-inventory-result.md`
- `projects/sk-am64b-r5f-early-boot/docs/remoteproc-ipc-only-inventory.md`
- `projects/sk-am64b-r5f-early-boot/docs/sk-am64b-r5f-remoteproc-dt-inventory.md`

### task-unit-2 local preparation

완료된 것:

- heartbeat minimal feature spec 정리
- SHM ABI draft 정리
- early-boot heartbeat first draft source 작성
- local buildable draft 검증 성공
- R5F multicore image generation helper 작성 및 local artifact 생성
- Linux appimage generation helper 작성 및 local artifact 생성
- Linux appimage staging dry-run helper 작성
- OSPI layout dry-run helper 작성

관련 provenance:

- `logs/provenance/r5f-early-boot/2026-06-04_early-heartbeat-draft-local-build.md`
- `logs/provenance/r5f-early-boot/2026-06-04_phase2_local-image-generation.md`

### local generated artifacts

현재 host 기준 주요 산출물:

- R5F image:
  - `out/sk-am64b-r5f-early-boot/images/r5f-early-heartbeat.mcelf`
  - `out/sk-am64b-r5f-early-boot/images/r5f-early-heartbeat.mcelf.hs_fs`
- Linux image:
  - `out/r5f-early-boot/linux-appimage-build/linux.mcelf.hs_fs`
  - `out/r5f-early-boot/linux-appimage-build/u-boot.img`

## 시도한 board-side 작업

### 1. Linux shell에서 직접 `/dev/mtd*` write 시도

이건 잘못된 방향이었다.

문제점:

- TI cfg는 absolute flash offset semantics를 사용한다.
- 우리는 `mtd0/mtd2/mtd5` 등 partition-relative write처럼 해석했다.
- 특히 `mtd0`에 composite image를 직접 만드는 식의 임의 조작이 들어갔다.

이건 guide semantics와 다르므로 더 이상 기준으로 삼지 않는다.

### 2. `uart_uniflash.py` 경로로 전환

이후 `uartd`를 stop 하고 UART boot mode에서 TI flashwriter/uniflash 경로를 사용했다.

#### 시도 A

- custom cfg에서 `am64x-evm` flashwriter
- `flash-phy-tuning-data` 포함
- 결과: flashwriter 전송은 되지만 `flash-phy-tuning-data`에서 실패

#### 시도 B

- `flash-phy-tuning-data` 제거
- 여전히 `am64x-evm` 계열 사용
- 결과: flashwriter 전송 후 첫 실제 file command 단계에서 실패

#### 시도 C

- `am64x-sk` flashwriter 사용
- 잘못해서 offset `0x0` image를 `sbl_ospi` 로 바꿈
- 결과: plain SBL 쪽에 가까운 동작으로 보이며 Linux chain을 타지 않음

#### 시도 D

- `am64x-sk` flashwriter 유지
- offset `0x0` image를 다시 `sbl_ospi_linux` 로 복구
- `flash-phy-tuning-data` 제거
- cfg:
  - `bsp/mcu-plus/configs/sbl_ospi_linux_sk-am64b_phase2_no-phy_linuxsbl.cfg`
- 결과: `uart_uniflash.py` 전체 단계 `SUCCESS`, `All commands from config file are executed !!!`

이게 현재 최신 board-side flashing 상태다.

## 지금 확인된 핵심 실패 증상

`uartd`를 다시 시작한 뒤 OSPI boot로 부팅을 보면,
UART 최신 출력은 여전히 다음 패턴에서 멈춘다.

```text
DMSC Firmware Version ...
KPI_DATA ...
App_loadLinuxImages ...
App_loadImages ...
Image loading done, switching to application ...
Starting linux and RTOS/Baremetal applications
BL31 banner
<no further output>
```

즉 현재 latest symptom은 여전히:

```text
SBL chain starts
BL31 starts
BL31 이후 handoff에서 정지
```

최근 세션에서 내가 한 실수:

- `runtime_log` 전체 누적 로그와 현재 boot 시도 로그를 섞어서 잘못 해석함
- 이후부터는 `uart_uart_tail` 최신 출력만 기준으로 판정함

## 중요한 deviation / correction history

다음은 우리가 guide와 어긋났다가 교정한 항목들이다.

1. `tispl.bin` 을 `u-boot-spl.bin-am64xx-evm` 로 alias해서 Linux appimage 입력으로 쓴 것
   - 교정: local raw SPL `out/u-boot/a53/spl/u-boot-spl.bin` 사용

2. partition-based write 모델을 guide semantics와 동등하다고 본 것
   - 교정: absolute offset model을 source of truth로 문서/절차에 다시 고정

3. `mtd0` 안에 composite image를 직접 만들어 write 한 것
   - 교정: guide-aligned cfg 기반 접근으로 전환

4. `DEVICE_TYPE=GP` 를 helper에서 강제한 것
   - 아직 완전히 정리된 것은 아니며, 다시 확인 필요

5. `am64x-evm` flashwriter / image 조합을 SK 보드에서 사용한 것
   - 교정: `am64x-sk` flashwriter 사용

6. `sbl_ospi` 와 `sbl_ospi_linux` 를 혼동한 것
   - 교정: latest UART uniflash cfg에서 `sbl_ospi_linux` 사용

## 지금 가장 가능성 높은 남은 문제 영역

현재는 다음이 가장 유력한 남은 문제 후보다.

1. **Linux appimage 내부 chain mismatch**
   - BL31/BL32/SPL/U-Boot proper provenance 또는 형식 mismatch
   - raw SPL 교체 후에도 BL31 stop이 유지됨

2. **guide image set과 current custom image set 차이**
   - TI example은 `ipc_rpmsg_echo_linux_system.release.mcelf.hs_fs` 를 multicore appimage로 사용
   - 우리는 custom `r5f-early-heartbeat.mcelf.hs_fs` 사용
   - Linux appimage 쪽도 local-generated 조합이라 exact TI example set과 다름

3. **HS-FS / image signing / expected artifact form 세부 mismatch**
   - 특히 local helper `gen-linux-appimage-for-sbl.sh` 안의 device type / input provenance를 재검토할 가치가 있음

## 지금 절대 다시 하면 안 되는 것

- `mtd0/mtd2/mtd5` partition-relative write를 TI cfg semantics와 같다고 간주
- `mtd0` composite image 생성
- `sbl_ospi` 를 Linux chain 시작 image 자리에 쓰기

## 다음 세션에서 가장 먼저 해야 할 것

1. **현재 latest cfg와 latest UART failure signature 재확인**
   - latest cfg: `bsp/mcu-plus/configs/sbl_ospi_linux_sk-am64b_phase2_no-phy_linuxsbl.cfg`
   - latest UART stop point: BL31 banner 이후 무출력

2. **latest OSPI contents를 다시 건드리기 전에, TI example chain과 우리 chain의 차이를 명시적 표로 비교**
   - offset `0x0` image
   - offset `0x80000` image
   - offset `0x300000` image
   - offset `0x800000` image
   - signed/unsigned / board variant / generated/prebuilt provenance

3. **`gen-linux-appimage-for-sbl.sh` 재검토**
   - 아직 helper 내부에 `DEVICE_TYPE=GP` override가 남아 있는지 확인하고 제거/교정할 것
   - Linux appimage를 가능한 한 TI guide example에 더 가깝게 재생성할지 검토

4. **필요하면 TI stock cfg를 더 직접적으로 따라가는 별도 retry cfg 생성**
   - 지금 cfg는 이미 상당히 가이드 쪽으로 돌렸지만, 아직 project artifact를 섞고 있음

5. **새 부팅 판정은 무조건 UART MCP latest tail만 기준으로 할 것**
   - `runtime_log` 전체 누적 로그로 섞어 읽지 말 것

## 지금 시점에서 다음 세션에 전달할 판단

```text
Phase2 local preparation and guide-aligned UART flashing path are ready and have been exercised.
The remaining blocker is not “how to flash”, but “why the flashed image chain still stops immediately after BL31”.
```

즉 다음 세션은 문서 정리보다
**BL31 이후 handoff chain mismatch 분석**에 바로 들어가면 된다.
