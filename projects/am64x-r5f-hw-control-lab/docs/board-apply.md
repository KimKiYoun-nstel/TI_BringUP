# 보드 적용 및 테스트 절차

## 목적

`am64x-r5f-hw-control-lab` 프로젝트를 SK-AM64B 보드에 배포하고, reboot 기반으로 `r5fss0-0` firmware를 적용한 뒤 A53 `r5ctl`로 Phase 1 RPMsg/GPIO hook 동작을 확인한다.

## 사전 조건

1. 보드 SSH 접속 가능
2. SDK/툴체인 환경 파일이 `tools/env/` 아래에 준비됨
3. 기존 baseline 복구 대상이 정상 상태임
4. `benchmark_server.service`, `rpmsg_json.service`가 기존 baseline용 서비스임을 이해함

## 1. 빌드

```bash
./tools/build/build-am64x-r5f-hw-control-lab.sh all
```

생성물:

- R5F firmware alias: `out/am64x-r5f-hw-control-lab/am64-main-r5f0_0-fw`
- A53 CLI: `out/am64x-r5f-hw-control-lab/a53/r5ctl`
- CCS workspace: `out/am64x-r5f-hw-control-lab/ccs_projects/`

## 2. Host에서 보드로 배포

```bash
./tools/install/deploy-am64x-r5f-hw-control-lab-host.sh 192.168.0.110
```

보드에 복사되는 경로:

- `/usr/lib/firmware/ti-bringup/am64x-r5f-hw-control-lab/am64-main-r5f0_0-fw`
- `/usr/local/bin/r5ctl`
- `/usr/local/sbin/am64x-r5f-hw-control-lab-manage.sh`

이 단계에서는 `/usr/lib/firmware/am64-main-r5f0_0-fw` symlink를 변경하지 않는다.

## 3. 보드 내부 적용

```bash
/usr/local/sbin/am64x-r5f-hw-control-lab-manage.sh apply
```

스크립트는 원본 firmware target/copy를 `/var/lib/ti-bringup/am64x-r5f-hw-control-lab/`에 보관하고, baseline 서비스를 중지한 뒤 symlink를 테스트 firmware로 바꾸고 재부팅한다.

runtime remoteproc stop/start는 이 프로젝트의 기본 적용 경로가 아니다.

## 4. 기능 확인

재부팅 후 다음 명령을 실행한다.

가능하면 먼저 baseline 서비스 정책을 lab mode로 적용한다. 권장 방식은 repo-managed overlay profile을 설치하는 것이다.

```bash
./tools/install/manage-sk-am64b-lab-service-policy.sh 192.168.0.110 overlay-apply
```

이 방식은 marker + drop-in 정책을 보드에 설치해서 서비스가 enabled 상태여도 boot 시 skip되게 만든다.

현재 rootfs 인스턴스만 빠르게 바꾸고 싶으면 runtime helper를 직접 써도 된다.

```bash
./tools/install/manage-sk-am64b-lab-service-policy.sh 192.168.0.110 apply
```

```bash
/usr/local/bin/r5ctl ping
/usr/local/bin/r5ctl status
/usr/local/bin/r5ctl gpio set 1
/usr/local/bin/r5ctl gpio toggle
/usr/local/bin/r5ctl gpio blink 3
/usr/local/bin/r5ctl trace
```

관리 스크립트를 통해 실행할 수도 있다.

```bash
/usr/local/sbin/am64x-r5f-hw-control-lab-manage.sh test ping
/usr/local/sbin/am64x-r5f-hw-control-lab-manage.sh test gpio set 0
```

성공 예시는 다음 형식이다.

```text
TX: PING
RX: OK PONG
```

`status` 응답에는 `core=78000000.r5f`, `service=rpmsg_chrdev`, `endpoint=14`, `gpio_candidate=MCU_GPIO0_8`이 포함되어야 한다.

## 5. GPIO 확인 시 주의

`MCU_GPIO0_8`은 firmware hook의 기본 후보이다. 현재 SysConfig에서는 `MCU_SPI1_D0` pad를 `MCU_GPIO0_8` mode 7로 설정한다. package ball 정보는 generated pinmux 주석 기준 `C7`로 확인되지만, board connector pin 번호는 이 문서에서 검증 완료로 취급하지 않는다. 실제 외부 회로 연결 전에는 schematic, pinmux, Linux 점유 여부, 계측 결과를 별도로 확인한다.

## 6. 복구

테스트 후 baseline으로 되돌린다.

```bash
/usr/local/sbin/am64x-r5f-hw-control-lab-manage.sh restore
```

복구도 symlink를 원본 target으로 되돌리고 재부팅하는 방식이다.
