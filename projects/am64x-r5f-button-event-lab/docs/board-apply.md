# 보드 반영 절차

이 프로젝트는 Phase 1에서 사용한 보드 운영 흐름을 그대로 따른다. 기본 절차는 산출물을 복사하고, active firmware symlink를 전환한 뒤, 재부팅하는 방식이다. runtime 중 `remoteproc stop/start`는 기본 배포 경로로 사용하지 않는다.

## Host 배포

```bash
./tools/install/install-kernel-to-sd.sh 192.168.0.110 dtb-only --reboot
./tools/build/build-am64x-r5f-button-event-lab.sh all
./tools/install/deploy-am64x-r5f-button-event-lab-host.sh 192.168.0.110
# Host에서 한 번에 apply까지 수행하는 선택 경로이며, 보드가 재부팅된다.
./tools/install/deploy-am64x-r5f-button-event-lab-host.sh 192.168.0.110 apply
```

Phase 4 SHM/VTM baseline에서는 **반드시 DTB deploy/reboot를 먼저 수행해야 한다.**
`deploy-am64x-r5f-button-event-lab-host.sh`는 firmware, `r5ctl`, manage script만 복사하며 DTB는 배포하지 않는다.
즉 old DTB 상태에서 `apply`만 수행하면 `0xa5800000`가 Linux 일반 RAM일 수 있으므로 사용하면 안 된다.

전체 요약은 `docs/phase4-shm-vtm-summary.md`를 참고한다.

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
