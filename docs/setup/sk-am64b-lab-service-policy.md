# SK-AM64B Lab Service Policy

## 목적

이 문서는 SK-AM64B에서 **R5F lab firmware 검증 시 Linux userspace baseline 서비스 자동기동 정책을 어떻게 다룰지**를 독립 절차로 정리한다.

핵심은 다음과 같다.

1. R5F firmware auto-boot와 A53 systemd service auto-start는 서로 다른 층이다.
2. 현재 TI prebuilt rootfs에는 baseline/demo 성격의 RPMsg 연동 서비스가 이미 설치되어 있고 enabled 상태다.
3. lab 검증 중에는 해당 서비스가 `rpmsg_chrdev` 채널을 점유하거나 lab firmware가 이해하지 못하는 payload를 보내 trace를 오염시킬 수 있다.
4. 따라서 firmware switching 절차와 별개로 **Linux 서비스 정책 자체를 독립적으로 관리**하는 것이 더 적절하다.

## 현재 보드 상태 의미

현재 보드에서 확인한 사실:

- `benchmark_server.service` = installed + enabled
- `rpmsg_json.service` = installed + enabled
- 둘 다 `WantedBy=multi-user.target`
- `rpmsg_json.service`에는 repo overlay drop-in이 있어 remoteproc/rpmsg 준비 완료를 기다린 뒤 시작됨

즉 현재 TI prebuilt rootfs 기준 정책은:

```text
service installed
service enabled
boot 시 auto-start
rpmsg_json.service는 start timing만 보강
```

이다.

## 현재 repo 정책 표현 형태

현재 repo에는 두 층이 공존한다.

1. **runtime helper**
   - 현재 보드 인스턴스에 `disable --now` 또는 `enable --now`를 적용
2. **overlay profile**
   - `rootfs/overlays/sk-am64b-lab-r5f/` 아래 marker와 drop-in을 repo에 남김
   - 최종 rootfs 재생성 시 참고 기준점이 되는 정책 정의

즉 runtime helper는 운영 상태를 바꾸고, overlay profile은 장기 히스토리를 남긴다.

## 방법별 차이

### 1. stop

```bash
systemctl stop benchmark_server.service rpmsg_json.service
```

의미:

- 현재 boot 세션에서만 중지
- reboot 후에는 다시 auto-start

### 2. disable --now

```bash
systemctl disable --now benchmark_server.service rpmsg_json.service
```

의미:

- 현재 세션 즉시 중지
- 이후 reboot에도 auto-start 안 함
- unit file은 rootfs에 남음
- 필요 시 수동 `start` 가능

이 방식은 **현재 rootfs 인스턴스의 운영 상태를 바꾸는 것**이고, repo에 자동 저장되지는 않는다.

### 3. enable --now

```bash
systemctl enable --now benchmark_server.service rpmsg_json.service
```

의미:

- baseline 정책 복구
- 현재 세션 즉시 시작
- 이후 reboot에도 auto-start

### 4. drop-in / condition / marker

repo overlay profile에 drop-in을 추가해:

- 특정 marker file이 있으면 skip
- lab mode일 때만 실행 안 함
- product mode일 때는 다시 auto-start

같은 정책을 만들 수 있다.

이 방식은 **repo에 남는 정책 정의**가 된다.

현재 repo에는 다음 profile이 추가되었다.

```text
rootfs/overlays/sk-am64b-lab-r5f/
  etc/ti-bringup/lab-r5f.mode
  etc/systemd/system/benchmark_server.service.d/lab-mode.conf
  etc/systemd/system/rpmsg_json.service.d/lab-mode.conf
```

동작:

- marker file `/etc/ti-bringup/lab-r5f.mode`가 존재하면
- `ConditionPathExists=!/etc/ti-bringup/lab-r5f.mode` 조건이 false가 되어
- 두 서비스는 installed/enabled 상태일 수 있어도 boot 시 skip된다.

### 5. package/rootfs 제외

최종 rootfs 생성 시:

- baseline service unit 자체를 포함하지 않거나
- 관련 binary/package를 제외

할 수 있다.

이건 가장 근본적인 방식이며, 저장공간 최적화나 제품화 단계에서 의미가 크다.

## 현 단계 권장 운용

현재 단계에서는 다음 순서를 권장한다.

1. TI prebuilt rootfs 유지
2. lab 검증 중에는 `disable --now` 기반으로 baseline service auto-start 해제
3. repo에는 별도 문서와 helper script로 변경 이력을 남김
4. 나중에 최종 rootfs 재생성 시 해당 이력을 바탕으로
   - 계속 포함하되 disabled 상태로 둘지
   - marker/drop-in 정책으로 둘지
   - 아예 package에서 제외할지
   결정

즉:

```text
disable --now = 현재 rootfs 상태 변경
repo 문서/helper = 나중에 rootfs 재생성 시 참고할 정책 이력
```

## Helper Script

현재 repo에는 다음 helper를 추가했다.

```bash
./tools/install/manage-sk-am64b-lab-service-policy.sh 192.168.0.110 status
./tools/install/manage-sk-am64b-lab-service-policy.sh 192.168.0.110 apply
./tools/install/manage-sk-am64b-lab-service-policy.sh 192.168.0.110 restore
./tools/install/manage-sk-am64b-lab-service-policy.sh 192.168.0.110 overlay-apply
./tools/install/manage-sk-am64b-lab-service-policy.sh 192.168.0.110 overlay-restore
```

동작:

- `status`: 현재 enable/active 상태와 unit definition 확인
- `apply`: `disable --now` 수행
- `restore`: `enable --now` 수행
- `overlay-apply`: repo-managed overlay profile을 보드에 설치하고 marker/drop-in 기반 lab mode 정책 적용
- `overlay-restore`: overlay profile을 제거하고 baseline auto-start 정책 복구

## 이 절차가 남기는 의미

이 helper와 문서는 다음을 위한 기준점이다.

1. TI prebuilt rootfs 대비 어떤 서비스를 lab mode에서 제외했는지 기록
2. 실제 보드에서 그 정책이 문제없이 동작했는지 검증
3. 최종 rootfs 재생성 시 package/overlay 정책으로 승격할 근거 확보

따라서 이 절차는 firmware switching의 부속물이 아니라, **Linux OS 서비스 정책 커스터마이징 절차**로 취급하는 것이 맞다.
