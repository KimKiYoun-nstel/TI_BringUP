# 보드 반영 절차

이 프로젝트는 Phase 1에서 사용한 보드 운영 흐름을 그대로 따른다. 기본 절차는 산출물을 복사하고, active firmware symlink를 전환한 뒤, 재부팅하는 방식이다. runtime 중 `remoteproc stop/start`는 기본 배포 경로로 사용하지 않는다.

## Host 배포

```bash
./tools/build/build-am64x-r5f-button-event-lab.sh all
./tools/install/deploy-am64x-r5f-button-event-lab-host.sh 192.168.0.110
# Optional one-step activation from host; this reboots the board.
./tools/install/deploy-am64x-r5f-button-event-lab-host.sh 192.168.0.110 apply
```

보드에서 기대하는 경로:

- Firmware: `/usr/lib/firmware/ti-bringup/am64x-r5f-button-event-lab/am64-main-r5f0_0-fw`
- A53 app: `/usr/local/bin/r5ctl`
- Manage script: `/usr/local/sbin/am64x-r5f-button-event-lab-manage.sh`

## 적용

```bash
/usr/local/sbin/am64x-r5f-button-event-lab-manage.sh status
/usr/local/sbin/am64x-r5f-button-event-lab-manage.sh apply
```

스크립트는 원래 firmware target/copy를 `/var/lib/ti-bringup/am64x-r5f-button-event-lab/`에 저장하고, `/usr/lib/firmware/am64-main-r5f0_0-fw`를 Phase 2 firmware로 가리키게 바꾼 뒤, baseline benchmark 서비스를 중지하고 `sync` 후 재부팅한다.

## 복구

```bash
/usr/local/sbin/am64x-r5f-button-event-lab-manage.sh restore
```

복구 시에는 firmware symlink를 저장된 baseline target으로 되돌리고, 저장된 copy를 복원하며, baseline 서비스를 다시 시작한 뒤 재부팅한다.
