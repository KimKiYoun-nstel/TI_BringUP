# SK-AM64B R5F remoteproc module sync 및 rpmsg startup race 해결

- 날짜: 2026-05-15
- 상태: Resolved on live board
- 관련 상세 조사:
  - [research note](file:///home/nstel/ti/TI_Bringup/docs/research/2026-05-15_am64x_remoteproc_empty_sysfs_after_module_load.md)
- 관련 증적:
  - [bringup resolution log](file:///home/nstel/ti/TI_Bringup/docs/bringup-logs/2026-05-15_sk-am64b_r5f_remoteproc_rpmsg_resolution.md)
  - [runtime verification log](file:///home/nstel/ti/TI_Bringup/logs/runtime/2026-05-15_sk-am64b_r5f_remoteproc_verification_log.md)

## 증상

R5F 동작 여부를 확인하려고 했지만, 처음에는 A53 Linux에서 R5F 제어 드라이버가 정상적으로 동작하지 않는 것처럼 보였다.

처음 확인된 현상:

- `modprobe ti_k3_r5_remoteproc` 실패
- `uname -r` 와 `/lib/modules/<release>` 불일치
- 어떤 관측 시점에는 `/sys/class/remoteproc/` 가 비어 있음
- `releasing ...` 로그가 보여 remoteproc registration 실패처럼 보임

## 1차 원인

첫 번째 실제 문제는 **커널 Image와 rootfs module tree 불일치**였다.

```text
running kernel: 6.18.13-gc21449208550
rootfs modules: /lib/modules/6.18.13-ti-00778-gc21449208550-dirty/
```

이 상태에서는 A53 Linux가 현재 커널 release에 맞는 `ti_k3_r5_remoteproc` 모듈을 찾을 수 없다.

## 1차 조치

현재 커널 release 기준으로 다음 모듈을 다시 배포했다.

- `ti_k3_r5_remoteproc.ko`
- `ti_k3_m4_remoteproc.ko`
- `rpmsg_char.ko`
- `rpmsg_ctrl.ko`

또한 modules deploy flow를 추가했다.

- [install-kernel-modules-to-sd.sh](file:///home/nstel/ti/TI_Bringup/tools/install/install-kernel-modules-to-sd.sh)
- [verify-kernel-modules-postdeploy.sh](file:///home/nstel/ti/TI_Bringup/tools/install/verify-kernel-modules-postdeploy.sh)

의미:

> A53 Linux가 R5F remoteproc 제어 드라이버를 현재 커널과 맞는 상태로 로드할 수 있게 만든 것

## 2차 관찰

모듈 동기화 후에도 처음에는 여전히 문제가 남아 보였다.

관측된 현상:

- `/sys/class/remoteproc/` 가 비어 있는 것처럼 보인 시점이 있었음
- `remoteproc ... releasing ...` 로그 관측

이때는 remoteproc 자체가 여전히 실패하는 것으로 해석될 수 있었다.

## 재조사 결과

live board를 clean reboot 후 다시 확인한 결과는 달랐다.

정상 확인된 것:

- `/sys/class/remoteproc/remoteproc0..4` 생성
- M4F + R5F 4개 코어 모두 `state=running`
- dmesg에서
  - `is available`
  - `Booting fw image`
  - `is now up`
  - `rpmsg host is online`
  확인

즉 clean boot 기준으로는 다음이 성립했다.

```text
A53 Linux 부팅 상태에서
R5F/M4F remoteproc 정상 등록 가능
TI 예제 firmware boot 가능
RPMsg host online 가능
```

## 최종 원인

실제 남은 문제는 remoteproc bring-up 자체가 아니라,

```text
rpmsg_json.service 가 remoteproc/rpmsg 준비 전에 너무 일찍 시작되는 startup timing race
```

였다.

boot timing 근거:

- `rpmsg_json.service` 시작: 약 `18s`
- `remoteproc1 is available`: 약 `26.6s`
- `rpmsg host is online`: 약 `26.7s`

즉 서비스가 remoteproc/rpmsg 준비보다 약 6~8초 빠르게 시작하고 있었다.

실패 로그:

```text
_rpmsg_char_find_rproc: 78000000.r5f device is mostly yet to be created!
Can't create an endpoint device: Bad address
```

## 최종 조치

rootfs overlay에 systemd override drop-in을 추가했다.

- [override.conf](file:///home/nstel/ti/TI_Bringup/rootfs/overlay/etc/systemd/system/rpmsg_json.service.d/override.conf)

핵심 보완:

- `remoteproc1/state == running` 될 때까지 대기
- `/dev/rpmsg_ctrl1` 생성까지 대기
- 실패 시 재시작

즉 `rpmsg_json.service` 를 **R5F remoteproc 및 rpmsg가 준비된 뒤에만 시작**하도록 바꿨다.

## 검증

보드에 override 적용 후 reboot 검증 완료.

확인 결과:

- `rpmsg_json.service` = `active (running)`
- `remoteproc0..4` = 모두 `running`
- `/dev/rpmsg*`, `/dev/rpmsg_ctrl*` 정상 생성
- `rpmsg_json` 로그에서 round-trip time 출력 및 결과 파일 생성 확인

## 결론

이 이슈의 큰 흐름은 다음과 같다.

1. R5F 동작 여부를 확인하려 함
2. 먼저 kernel/modules 동기화 문제가 드러남
3. modules deploy로 A53 Linux의 remoteproc 제어 드라이버 로드 문제 해결
4. 이후 remoteproc 자체 문제처럼 보였으나, clean reboot 재검증으로 부팅 steady-state는 정상임을 확인
5. 실제 잔여 문제는 `rpmsg_json.service` startup race 였고, rootfs overlay로 보완 후 해결

즉 이 이슈는

```text
R5F bring-up 실패 이슈
```

가 아니라 최종적으로는

```text
kernel/modules sync + rpmsg userspace startup ordering 이슈
```

로 정리하는 것이 맞다.

## 후속 메모

- 향후 유사 이슈는 먼저 `uname -r` 와 `/lib/modules/<release>` 일치 여부를 확인한다.
- remoteproc 문제로 보이면 clean reboot 후 `/sys/class/remoteproc/*/state` 를 먼저 확인한다.
- RPMsg userspace 실패는 remoteproc bring-up 실패와 분리해서 본다.
- board reboot/boot 타이밍 판단에는 `logs/runtime_log` 를 우선 참고하고, OS 부팅 이후 steady-state 동작은 journal/sysfs/service 상태와 함께 본다.
