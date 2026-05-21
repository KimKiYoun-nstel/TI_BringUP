# AM64x R5F Button Event Lab

이 프로젝트는 SK-AM64B button-event bring-up을 위한 Phase 2 실험 프로젝트다. Phase 1 프로젝트 구조를 참고해 별도 프로젝트로 분리했으며, `projects/am64x-r5f-hw-control-lab`은 reference-only로 유지하고 이번 구현에는 직접 포함하지 않는다.

Phase 2는 Phase 1의 반대 방향 경로를 검증한다.

```text
SK-AM64B SW1 -> MCU_GPIO0_6 -> R5F GPIO interrupt -> RPMsg text event -> A53 r5ctl
```

## 주요 속성

- R5F project: `am64x_r5f_button_event_lab_r5fss0_0_freertos_ti_arm_clang`
- RPMsg service: `rpmsg_chrdev`
- RPMsg endpoint: `14`
- A53 binary: `r5ctl`
- Button input: `SW1` on `MCU_GPIO0_6`
- Active-low mapping: raw `0`은 pressed/falling, raw `1`은 released/rising
- Protocol: text only

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
```

deploy 단계는 firmware, `r5ctl`, board manage script를 복사한다. 기본 경로에서는 runtime 중 `remoteproc stop/start`를 수행하지 않는다.

## 보드에서 직접 확인할 명령

```bash
/usr/local/sbin/am64x-r5f-button-event-lab-manage.sh apply
/usr/local/sbin/am64x-r5f-button-event-lab-manage.sh test ping
/usr/local/sbin/am64x-r5f-button-event-lab-manage.sh test button status
/usr/local/sbin/am64x-r5f-button-event-lab-manage.sh test button wait 5000
/usr/local/bin/r5ctl button monitor
/usr/local/sbin/am64x-r5f-button-event-lab-manage.sh restore
```
