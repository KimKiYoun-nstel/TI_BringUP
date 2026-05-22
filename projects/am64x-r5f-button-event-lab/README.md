# AM64x R5F Button Event Lab

이 프로젝트는 SK-AM64B button-event bring-up을 위해 시작한 Phase 2 실험 프로젝트이며,
현재는 이를 Phase 3 상태 모델 / command protocol baseline으로 확장한 상태다.
`projects/am64x-r5f-hw-control-lab`은 Phase 1 output command 구현을 참고하는 reference-only 자산으로 유지한다.

현재 baseline은 다음 두 경로와 Phase 4 SHM/VTM telemetry까지 함께 다룬다.

```text
SK-AM64B SW1 -> MCU_GPIO0_6 -> R5F GPIO interrupt -> RPMsg text event -> A53 r5ctl
A53 r5ctl -> RPMsg text command -> R5F -> MCU_GPIO0_8 output control
R5F -> reserved-memory SHM status block -> A53 r5ctl shm-status
```

## 주요 속성

- R5F project: `am64x_r5f_button_event_lab_r5fss0_0_freertos_ti_arm_clang`
- RPMsg service: `rpmsg_chrdev`
- RPMsg endpoint: `14`
- A53 binary: `r5ctl`
- Button input: `SW1` on `MCU_GPIO0_6`
- Output GPIO: `MCU_GPIO0_8`
- Active-low mapping: raw `0`은 pressed/falling, raw `1`은 released/rising
- Protocol: text only
- Phase 4 SHM: SK-AM64B DTS의 `r5f-status-shm@a5800000`, size `0x1000`
- Phase 4 temperature telemetry: R5F가 `main_vtm0` sensor index `0/1`의 raw code와 milli-Celsius 값을 SHM에 기록
- Compare path: `r5ctl shm-status`가 Linux `main0_thermal` / `main1_thermal`과 delta를 같이 출력
- Phase 4 summary: `docs/phase4-shm-vtm-summary.md`

## 디렉터리 구조

```text
projects/am64x-r5f-button-event-lab/
  a53/                 A53 Linux용 r5ctl source
  board/               보드 측 apply/restore/test script
  docs/                protocol, board apply, test, ownership, issues, completion 문서
  r5f/                 R5F firmware, SysConfig, CCS projectspec
```

## 빌드

```bash
./tools/build/build-am64x-r5f-button-event-lab.sh r5f
./tools/build/build-am64x-r5f-button-event-lab.sh a53
./tools/build/build-am64x-r5f-button-event-lab.sh all
```

빌드 산출물은 Phase 1과 충돌하지 않도록 `out/am64x-r5f-button-event-lab/` 아래에 생성한다.

## 배포

```bash
./tools/install/deploy-am64x-r5f-button-event-lab-host.sh 192.168.0.110
# Host에서 한 번에 apply까지 수행하는 선택 경로이며, 보드가 재부팅된다.
./tools/install/deploy-am64x-r5f-button-event-lab-host.sh 192.168.0.110 apply

# Phase 4 SHM slice는 DTB에 reserved-memory가 먼저 반영되어 있어야 한다.
./tools/install/install-kernel-to-sd.sh 192.168.0.110 dtb-only --reboot
```

deploy 단계는 firmware, `r5ctl`, board manage script를 복사한다. 기본 경로에서는 runtime 중 `remoteproc stop/start`를 수행하지 않는다.
단, **Phase 4 SHM을 실제로 사용하려면 새 DTB가 먼저 부팅되어 `r5f-status-shm@a5800000`가 reserved-memory로 잡혀 있어야 한다.** old DTB 상태에서 새 firmware만 적용하면 R5F가 Linux 일반 RAM을 덮어쓸 수 있으므로 `dtb-only` deploy/reboot를 선행해야 한다.

## 보드에서 직접 확인할 명령

```bash
/usr/local/sbin/am64x-r5f-button-event-lab-manage.sh apply
/usr/local/sbin/am64x-r5f-button-event-lab-manage.sh test ping
/usr/local/sbin/am64x-r5f-button-event-lab-manage.sh test status
/usr/local/sbin/am64x-r5f-button-event-lab-manage.sh test gpio list
/usr/local/sbin/am64x-r5f-button-event-lab-manage.sh test gpio get mcu_gpio0_8
/usr/local/sbin/am64x-r5f-button-event-lab-manage.sh test gpio set mcu_gpio0_8 1
/usr/local/sbin/am64x-r5f-button-event-lab-manage.sh test button status
/usr/local/sbin/am64x-r5f-button-event-lab-manage.sh test button wait 5000
/usr/local/bin/r5ctl shm-status
/usr/local/bin/r5ctl event monitor
/usr/local/bin/r5ctl button monitor
/usr/local/sbin/am64x-r5f-button-event-lab-manage.sh restore
```
