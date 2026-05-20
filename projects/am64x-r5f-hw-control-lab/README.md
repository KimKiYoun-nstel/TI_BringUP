# AM64x R5F H/W Control Lab

이 디렉터리는 `projects/sk-am64b-rpmsg-test` echo baseline에서 파생한 **Phase 1 하드웨어 제어 실습 프로젝트**이다. A53 Linux의 단발 실행 CLI `r5ctl`이 RPMsg text command를 보내고, `r5fss0-0` R5F firmware가 명령을 해석해서 trace와 GPIO 제어 hook을 실행한다.

## 범위

- 대상 remote core: `r5fss0-0` / `78000000.r5f`
- Linux firmware name: `am64-main-r5f0_0-fw`
- RPMsg transport: `libti_rpmsg_char`
- RPMsg remote id: `R5F_MAIN0_0`
- RPMsg service: `rpmsg_chrdev`
- RPMsg endpoint: `14`
- A53 CLI: `r5ctl`
- 기본 GPIO 후보: `MCU_GPIO0_8`

`MCU_GPIO0_8`은 Phase 1 제어 hook의 기본 후보로만 둔다. 이 프로젝트 문서는 보드 connector pin 번호가 실측 검증되었다고 주장하지 않는다.

## 구조

```text
projects/am64x-r5f-hw-control-lab/
  README.md
  docs/
    board-apply.md
    completion.md
    issues.md
    plan.md
    protocol.md
    test-procedure.md
  board/
    am64x-r5f-hw-control-lab-manage.sh
  r5f/
    example.syscfg
    main.c
    ipc_rpmsg_echo.c
    ti-arm-clang/example.projectspec
  a53/
    Makefile
    src/main.c
tools/build/build-am64x-r5f-hw-control-lab.sh
tools/install/deploy-am64x-r5f-hw-control-lab-host.sh
```

## 빌드

```bash
./tools/build/build-am64x-r5f-hw-control-lab.sh r5f
./tools/build/build-am64x-r5f-hw-control-lab.sh a53
./tools/build/build-am64x-r5f-hw-control-lab.sh all
```

빌드 결과는 `out/am64x-r5f-hw-control-lab/` 아래에 생성된다.

## Host 배포

```bash
./tools/install/deploy-am64x-r5f-hw-control-lab-host.sh 192.168.0.110
```

이 단계는 보드로 firmware, `r5ctl`, 보드 내부 관리 스크립트를 복사할 뿐이며 활성 firmware symlink는 변경하지 않는다.

## 보드 내부 적용 / 테스트 / 복구

```bash
/usr/local/sbin/am64x-r5f-hw-control-lab-manage.sh apply
/usr/local/sbin/am64x-r5f-hw-control-lab-manage.sh test ping
/usr/local/sbin/am64x-r5f-hw-control-lab-manage.sh test status
/usr/local/sbin/am64x-r5f-hw-control-lab-manage.sh test gpio set 1
/usr/local/sbin/am64x-r5f-hw-control-lab-manage.sh restore
```

적용과 복구는 기존 baseline과 동일하게 reboot 기반으로 수행한다. runtime remoteproc stop/start는 기본 workflow가 아니다.

GPIO 후보는 firmware boot 시점에 바로 구동하지 않으며, 첫 GPIO 명령이 들어올 때 하드웨어 설정과 출력 동작을 시작한다.

## 문서

- [docs/protocol.md](docs/protocol.md): RPMsg text command 규약
- [docs/board-apply.md](docs/board-apply.md): 보드 적용 및 테스트 절차
- [docs/completion.md](docs/completion.md): 현재 검증 결과와 남은 수동 검증 항목
- [docs/issues.md](docs/issues.md): 제약과 미검증 항목
- [docs/test-procedure.md](docs/test-procedure.md): 외부 LED/멀티미터 기준 실측 절차
