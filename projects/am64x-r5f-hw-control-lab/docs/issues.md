# 제약 및 미검증 항목

## 1. GPIO connector pin 미검증

현재 코드의 기본 후보는 `MCU_GPIO0_8`이다. 다만 이 repo 변경만으로 SK-AM64B connector의 특정 pin 번호가 검증되었다고 볼 수 없다. 문서, CLI 응답, trace에서는 `candidate`라는 표현을 유지한다.

## 2. SysConfig GPIO pinmux

현재 `example.syscfg`에는 GPIO module이 추가되어 있고, `MCU_GPIO0_8`을 위해 `MCU_SPI1_D0` pad를 mode 7 output으로 설정한다. generated 결과 기준으로 package ball 주석은 `C7`이다. 다만 이는 SoC/package pinmux 확인까지의 범위이며, board connector pin 번호와 외부 배선 검증은 여전히 남아 있다.

또한 generated `GPIO_init()`은 boot 시점에 해당 GPIO를 low로 초기화할 수 있으므로, 외부 LED/계측 장비 연결 전에는 회로 영향을 고려해야 한다.

## 3. Linux-owned resource 회피

Phase 1에서는 Linux console인 `ttyS2`, Linux LED subsystem, I2C 장치, Ethernet, Linux가 consumer로 잡은 GPIO를 R5F 제어 대상으로 삼지 않는다.

## 4. remoteproc 번호

문서와 스크립트는 `78000000.r5f`와 firmware name `am64-main-r5f0_0-fw`를 기준으로 설명한다. `remoteprocN` 번호는 probe 순서에 따라 바뀔 수 있으므로 고정값으로 의존하지 않는다.

## 5. SysConfig IPC 생성 코드 패치

기존 baseline과 동일하게 MCU+ SDK SysConfig가 `&gIpcSharedMem[]` 형태의 잘못된 IPC 코드를 생성할 수 있다. 새 build helper도 생성된 `ti_drivers_config.c`를 `&gIpcSharedMem[0]`으로 패치한 뒤 `gmake`를 다시 실행한다.

## 6. Live-board 검증 상태

이 문서는 절차와 예상 형식을 제공하지만, 이번 repo 편집만으로 live-board GPIO 전압 변화나 connector mapping이 검증되었다고 기록하지 않는다. 실제 보드 결과는 별도 로그로 남긴다.

## 7. Baseline 서비스 잡음

lab firmware 적용 후에도 `benchmark_server.service`와 `rpmsg_json.service`가 재부팅 뒤 다시 올라오면, firmware trace에 반복적인 `ERR UNKNOWN_CMD`가 남을 수 있다. 이는 baseline userspace가 `rpmsg_chrdev` 채널로 lab firmware가 이해하지 못하는 payload를 보내기 때문이다.

따라서 전용 lab 검증 시에는 다음을 먼저 실행하는 편이 좋다.

```bash
systemctl stop benchmark_server.service rpmsg_json.service || true
```
