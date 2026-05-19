# SK-AM64B RPMsg 테스트 프로젝트 계획

## 목표

repo 안에서 관리되는 RPMsg 검증용 프로젝트 2개를 만든다.

- R5F firmware (`r5fss0-0` 대상)
- A53 Linux userspace 테스트 앱

최종 목표는 실제 SK-AM64B 보드에서 두 프로젝트가 RPMsg로 임의 payload를 주고받고, 검증 후 보드를 기존 benchmark baseline으로 되돌리는 것이다.

## 재사용하는 기존 자산

- MCU+ SDK: `workspace/mcu_plus_sdk_am64x_12_00_00_27`
- Processor SDK Linux devkit/toolchain: `~/ti/am64x/ti-processor-sdk-linux-am64xx-evm-12.00.00.07.04`
- 기존 board SSH / remoteproc deploy 흐름

## 실행 순서

1. repo-managed R5F/A53 프로젝트 구조를 만든다.
2. R5F는 Linux IPC가 활성화된 단일 코어 echo firmware로 구성한다.
3. A53는 `libti_rpmsg_char` 기반 userspace 테스트 앱으로 구성한다.
4. 양쪽 프로젝트를 기존 SDK/툴을 이용해 빌드한다.
5. R5F firmware를 `am64-main-r5f0_0-fw`로 보드에 반영한다.
6. 재부팅 후 A53 앱으로 payload를 전송한다.
7. echo 응답을 확인한다.
8. 원래 benchmark firmware를 복구한다.

## 핵심 검증 기준

- remoteproc boot 로그로 새 R5F firmware 로드가 확인된다.
- A53 앱이 보낸 payload와 동일한 문자열이 R5F에서 echo되어 돌아온다.
- 테스트 후 원래 benchmark firmware와 관련 서비스가 정상 복구된다.
