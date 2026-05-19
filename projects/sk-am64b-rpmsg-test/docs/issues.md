# 중요 이슈

## 1. `rpmsg_json.service`가 remoteproc 번호에 하드코딩되어 있었다

기존 override는 다음 두 값을 기다리도록 되어 있었다.

- `/sys/bus/platform/devices/78000000.r5f/remoteproc/remoteproc1/state`
- `/dev/rpmsg_ctrl1`

문제점:

- probe 순서가 바뀌면 `78000000.r5f`가 `remoteproc0`이 될 수 있음
- 이 경우 firmware는 정상이어도 `rpmsg_json.service`가 잘못된 번호를 기다리며 실패함

적용한 수정:

- `78000000.r5f` 아래의 `remoteproc*/state` 중 하나라도 `running`이면 통과
- `/dev/rpmsg_ctrl*`가 하나라도 있으면 통과

관련 파일:

- `rootfs/overlay/etc/systemd/system/rpmsg_json.service.d/override.conf`

## 2. MCU+ SDK SysConfig가 잘못된 IPC 코드를 생성한다

Linux IPC 예제에서 생성된 `ti_drivers_config.c` 안에 다음 코드가 들어갔다.

```c
&gIpcSharedMem[]
```

이 코드는 컴파일되지 않는다.

대응:

- R5F 빌드 helper가 generated file을 패치한 뒤 직접 `gmake`로 재빌드하도록 구성했다.

관련 helper:

- `tools/build/build-sk-am64b-rpmsg-test.sh`

## 3. UART-only `hello_world`는 이 보드 검증 경로에 적합하지 않았다

기존 `hello_world` 테스트는 firmware가 실제로 로드됐다는 사실은 보여줬지만, 기대했던 UART 문자열은 `logs/runtime_log`에서 확인되지 않았다.

이 보드와 현재 운용 구조에서는 UART-only 검증보다 RPMsg payload 검증이 더 신뢰성이 높았다.

## 4. stock `ipc_rpmsg_echo`는 단일 코어 교체 검증용 예제가 아니다

기존 `ipc_rpmsg_echo`는 multi-core system project 전제라서, 현재 benchmark firmware 레이아웃에서 `r5fss0-0`만 바꿔 넣는 방식과 맞지 않았다.

그래서 최종적으로는 `ipc_rpmsg_echo_linux` 개념을 기반으로,

- 단일 R5F0-0 firmware
- 단일 A53 userspace 테스트 앱

조합으로 재구성했다.

## 5. 원본 benchmark firmware는 별도 원본 백업을 유지해야 한다

여러 번 실험하면 rolling backup이 테스트 firmware로 덮일 수 있다.

그래서 설치 helper는 다음 두 백업을 유지한다.

- rolling backup: `am64-main-r5f0_0-fw.ti_bringup_backup`
- 원본 백업: `am64-main-r5f0_0-fw.ti_bringup_orig`

복구 시에는 원본 백업을 우선 사용한다.

## 6. runtime remoteproc stop/start는 운영 경로에서 제외했다

실보드에서 `echo stop > .../state` 는 `Device or resource busy`로 실패했고, 관련 services/userspace를 내려도 동일 현상이 재현되었다.

원인:

- userspace RPMsg endpoint 점유
- 기존 benchmark 서비스와의 얽힘

대응:

- 최종 운영 모델에서는 runtime stop/start를 사용하지 않는다.
- 테스트 firmware 적용과 baseline 복구는 reboot 기반 apply/restore로 고정한다.

즉, runtime graceful restart는 현재 보드/SDK 조합에서 검증된 경로가 아니므로 운영 절차에서 제외했다.

## 7. benchmark baseline 서비스는 이번 프로젝트의 일부가 아니다

다음 서비스는 TI benchmark baseline용 Linux 서비스다.

- `benchmark_server.service`
- `rpmsg_json.service`

이번 프로젝트는 이 서비스들을 대체하지 않는다.
다만 baseline도 `rpmsg_chrdev` 기반 RPMsg 채널을 사용하므로, 테스트 firmware 적용 중에는 채널/endpoint 점유 충돌을 피하기 위해 관련 서비스를 중지한다.
