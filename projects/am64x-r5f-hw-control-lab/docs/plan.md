# Phase 1 개발 계획

## 목표

`projects/sk-am64b-rpmsg-test` echo baseline을 별도 프로젝트로 파생하여, A53 Linux가 control plane 역할을 하고 R5F `r5fss0-0` firmware가 RPMsg command dispatcher와 GPIO 제어 hook을 제공하는 실습 baseline을 만든다.

## Phase 1 범위

1. A53 `r5ctl` CLI를 repo에서 빌드한다.
2. R5F firmware는 `rpmsg_chrdev` endpoint `14`를 announce한다.
3. CLI 명령 `ping`, `status`, `gpio set`, `gpio toggle`, `gpio blink`, `trace`를 제공한다.
4. R5F는 `PING`, `STATUS`, `GPIO_SET`, `GPIO_TOGGLE`, `GPIO_BLINK` text command를 처리한다.
5. `DebugP_log` trace에는 `[AM64X R5F HWLAB]` prefix를 사용한다.
6. firmware 적용과 복구는 기존 검증 흐름과 동일하게 reboot 기반으로 유지한다.

## GPIO 방침

기본 후보는 `MCU_GPIO0_8`이다. connector pin 번호와 외부 회로 동작은 별도 계측 전까지 미검증으로 둔다. 확실한 SysConfig pinmux 근거가 확보되면 `example.syscfg`에 GPIO module과 pinmux를 추가한다.

## 제외 항목

- runtime remoteproc stop/start를 기본 workflow로 사용하지 않는다.
- Linux console `ttyS2`, Linux-owned LED/I2C/Ethernet 자원을 R5F 제어 대상으로 삼지 않는다.
- live-board 검증 전에는 성공 결과를 완료 문서로 기록하지 않는다.
