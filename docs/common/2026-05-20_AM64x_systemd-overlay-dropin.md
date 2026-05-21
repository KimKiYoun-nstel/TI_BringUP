# AM64x systemd overlay/drop-in 방식 정리

Date: 2026-05-20  
Board: AM64x common  
Category: docs/common/  
Status: Completed

## Summary

Embedded Linux BSP에서 `systemd` 서비스 정책을 커스터마이징할 때는 원본 unit 파일을 직접 수정하기보다 `/etc/systemd/system/<unit>.d/*.conf` 형태의 drop-in overlay를 사용하는 방식이 일반적이다.

이 방식은 TI Processor SDK 또는 Yocto rootfs가 제공하는 원본 unit을 유지하면서, 커스텀 보드/제품별 정책만 별도 파일로 관리할 수 있게 해준다. SK-AM64B 기반 리허설 단계에서도 R5F firmware loader, RPMsg userspace app, benchmark service, debug service 같은 항목에 적용하기 좋다.

## Context

현재 작업 흐름은 SK-AM64B에서 Linux userspace service 구성을 실험하면서, 추후 커스텀 보드 BSP에 반영할 수 있는 관리 패턴을 정리하는 단계이다.

부트 전체 흐름에서 systemd overlay는 다음 위치에 해당한다.

```text
Boot ROM
  -> tiboot3/R5 SPL
  -> SYSFW
  -> ATF/OP-TEE
  -> A53 SPL
  -> U-Boot proper
  -> Linux kernel + Device Tree
  -> RootFS mount
  -> systemd userspace service policy
```

즉, `systemd` overlay는 하드웨어 초기화 자체를 담당하는 단계가 아니라, Linux 부팅 이후 userspace service 실행 조건, 순서, 환경변수, 재시작 정책 등을 정의하는 영역이다.

## Knowledge

### 1. overlay/drop-in의 기본 구조

원본 unit은 보통 다음 위치 중 하나에 존재한다.

```text
/lib/systemd/system/<unit>.service
/usr/lib/systemd/system/<unit>.service
/etc/systemd/system/<unit>.service
```

원본 unit을 직접 수정하지 않고, 다음 위치에 추가 설정을 둔다.

```text
/etc/systemd/system/<unit>.service.d/override.conf
```

예시:

```text
/lib/systemd/system/rpmsg_json.service
/etc/systemd/system/rpmsg_json.service.d/override.conf
```

`systemd`는 원본 unit을 먼저 읽고, 이후 `.d/*.conf` 파일을 읽어 설정을 병합한다. 이 때문에 원본 위에 정책을 덧씌운다는 의미에서 overlay 또는 drop-in override라고 부른다.

### 2. BSP 관점에서 원본 unit을 직접 수정하지 않는 이유

TI SDK, Yocto, Debian package, custom rootfs package가 제공하는 파일을 직접 수정하면 다음 문제가 생긴다.

- SDK/rootfs 업데이트 시 수정사항이 사라질 수 있음
- 원본과 커스텀 변경분의 차이를 추적하기 어려움
- 커스텀 보드별 정책과 vendor 기본 정책이 섞임
- 추후 Yocto recipe 또는 bbappend로 제품화할 때 변경 범위가 불명확해짐

따라서 실무에서는 다음처럼 영역을 나누는 것이 좋다.

```text
Vendor/BSP 기본 영역:
  /lib/systemd/system/
  /usr/lib/systemd/system/

Board/Product 커스터마이징 영역:
  /etc/systemd/system/<unit>.d/*.conf
```

### 3. 자주 사용하는 drop-in 항목

#### ConditionPathExists

특정 파일이나 디렉터리가 존재할 때만 서비스를 실행한다.

```ini
[Unit]
ConditionPathExists=/sys/class/remoteproc/remoteproc0
```

RPMsg, remoteproc, 특정 device node 기반 서비스에 유용하다.

#### ConditionPathExistsGlob

패턴에 맞는 경로가 있을 때만 서비스를 실행한다.

```ini
[Unit]
ConditionPathExistsGlob=/dev/rpmsg*
```

주의: RPMsg device node는 R5F firmware가 올라간 뒤 늦게 생성될 수 있다. 이 경우 `ConditionPathExistsGlob`만으로는 타이밍 문제가 생길 수 있으며, `udev rule`, `systemd.path`, 또는 wait script가 필요할 수 있다.

#### After / Wants / Requires

서비스 실행 순서와 의존성을 제어한다.

```ini
[Unit]
After=remoteproc-init.service
Wants=remoteproc-init.service
```

의미 차이:

```text
After=      실행 순서만 지정
Wants=      함께 시작되면 좋지만 실패해도 현재 서비스는 계속 가능
Requires=   강한 의존성. 대상 실패 시 현재 서비스도 영향 받음
```

Bring-up 초기에는 `Requires=`를 과하게 사용하면 연쇄 실패가 발생해 디버깅이 어려워질 수 있다. 초기 실험 단계에서는 `After=` + `Condition*` 조합이 더 안전하다.

#### Environment

서비스에 환경변수를 추가한다.

```ini
[Service]
Environment=RPMSG_DEVICE=/dev/rpmsg_ctrl0
Environment=LOG_LEVEL=debug
```

보드별 device node, firmware name, log level 등을 외부화할 때 유용하다.

#### ExecStartPre

본 서비스 실행 전 검증 또는 준비 명령을 실행한다.

```ini
[Service]
ExecStartPre=/bin/test -e /dev/rpmsg_ctrl0
```

복잡한 로직은 unit 파일 안에 직접 넣기보다 별도 script로 분리하는 것이 좋다.

```ini
[Service]
ExecStartPre=/usr/local/bin/check-rpmsg-ready.sh
```

#### ExecStart 변경 시 주의

`ExecStart=`는 drop-in에서 새로 지정할 때 기존 값을 먼저 비워야 한다.

```ini
[Service]
ExecStart=
ExecStart=/usr/bin/my_custom_rpmsg_server --device /dev/rpmsg_ctrl0
```

첫 번째 빈 `ExecStart=`는 기존 실행 명령을 제거한다. 두 번째 줄이 새 실행 명령이다.

## Decision

- 원본 `systemd` unit 파일은 가능하면 직접 수정하지 않는다.
- 보드/제품별 정책은 `/etc/systemd/system/<unit>.d/override.conf` 형태의 drop-in overlay로 관리한다.
- SK-AM64B 리허설 단계에서는 R5F/RPMsg 관련 userspace service 제어에 overlay 방식을 우선 적용한다.
- Yocto 제품화 단계에서는 동일한 overlay 파일을 recipe 또는 bbappend를 통해 rootfs에 포함시키는 방향으로 관리한다.

## Assumption

- 현재 rootfs는 `systemd` 기반으로 동작한다고 가정한다.
- TI Processor SDK 또는 Yocto 기반 rootfs에서 제공되는 원본 unit은 vendor/BSP 영역으로 간주한다.
- 커스텀 보드 BSP에서는 userspace service 정책이 보드별로 달라질 수 있으므로 overlay 파일을 별도 artifact로 관리하는 것이 유리하다.

## Open Question

- 현재 SK-AM64B rootfs에서 실제로 overlay 적용 대상이 될 service 목록을 확인해야 한다.
- `rpmsg_json.service`, `benchmark_server.service`, custom R5F service 등의 원본 unit 경로와 실행 순서를 확인해야 한다.
- RPMsg device node 생성 타이밍이 service start 시점보다 늦는 경우 `udev rule`, `systemd.path`, wait script 중 어떤 방식을 표준으로 삼을지 결정해야 한다.

## Action Item

1. 현재 보드에서 systemd unit 원본과 drop-in 경로를 확인한다.

```bash
systemctl cat <unit>
systemctl show -p FragmentPath -p DropInPaths <unit>
```

2. 실험 대상 service에 drop-in overlay를 생성한다.

```bash
sudo systemctl edit <unit>
```

3. 변경 후 systemd 설정을 다시 로드하고 service를 재시작한다.

```bash
sudo systemctl daemon-reload
sudo systemctl restart <unit>
```

4. 적용 결과를 확인한다.

```bash
systemctl cat <unit>
systemctl status <unit>
journalctl -u <unit> -b
```

5. 검증된 `override.conf`는 repo에 보드 정책 artifact로 저장한다.

## Board Note

### AM64x common

이 내용은 SK-AM64B에만 한정되지 않고, AM64x 계열 커스텀 보드 BSP 전반에 적용 가능한 userspace service 관리 패턴이다.

### SK-AM64B

SK-AM64B에서는 다음 항목에 overlay 적용을 검토할 수 있다.

```text
rpmsg_json.service
benchmark_server.service
custom-r5f-app.service
remoteproc firmware loader service
GPIO/RPMsg test service
```

R5F/RPMsg 관련 서비스는 Linux kernel boot 이후 remoteproc 상태, firmware 준비 여부, RPMsg endpoint 생성 여부에 따라 실행 조건이 달라질 수 있다. 따라서 단순 `enable`보다 조건 기반 실행 정책이 더 안전하다.

## Artifact

### 예시: RPMsg service 조건 추가

```ini
# /etc/systemd/system/rpmsg_json.service.d/override.conf
[Unit]
ConditionPathExists=/sys/class/remoteproc/remoteproc0
After=remoteproc-init.service

[Service]
Environment=RPMSG_DEVICE=/dev/rpmsg_ctrl0
ExecStartPre=/bin/test -e /dev/rpmsg_ctrl0
```

### 예시: ExecStart 교체

```ini
# /etc/systemd/system/rpmsg_json.service.d/override.conf
[Service]
ExecStart=
ExecStart=/usr/bin/my_custom_rpmsg_server --device /dev/rpmsg_ctrl0 --log-level debug
```

### 예시: 복잡한 준비 로직을 script로 분리

```ini
# /etc/systemd/system/rpmsg_json.service.d/override.conf
[Service]
ExecStartPre=/usr/local/bin/check-rpmsg-ready.sh
```

```bash
#!/bin/sh
set -eu

test -e /sys/class/remoteproc/remoteproc0
test -e /dev/rpmsg_ctrl0
```

## Commands

```bash
# 최종 병합된 unit 확인
systemctl cat <unit>

# drop-in 생성/수정
sudo systemctl edit <unit>

# systemd 설정 재로드
sudo systemctl daemon-reload

# 서비스 상태 확인
systemctl status <unit>

# 현재 부팅 이후 해당 서비스 로그 확인
journalctl -u <unit> -b

# unit dependency 확인
systemctl list-dependencies <unit>

# unit 원본 파일과 drop-in 경로 확인
systemctl show -p FragmentPath -p DropInPaths <unit>
```

## Verification Points

성공적으로 overlay가 적용되면 다음을 확인할 수 있어야 한다.

```bash
systemctl cat <unit>
```

출력에서 원본 unit 뒤에 다음과 같은 drop-in 경로가 함께 표시된다.

```text
# /etc/systemd/system/<unit>.service.d/override.conf
```

`systemctl show`에서도 drop-in 경로가 확인되어야 한다.

```bash
systemctl show -p FragmentPath -p DropInPaths <unit>
```

서비스 실행 실패 시에는 다음을 우선 확인한다.

```bash
journalctl -u <unit> -b
systemctl status <unit>
```

의심 지점:

- `ConditionPathExists` 대상 경로가 실제로 존재하지 않음
- RPMsg device node 생성 시점이 service start보다 늦음
- `After=`는 순서만 보장하고 device 준비 완료를 보장하지 않음
- `Requires=`로 인해 의존 service 실패가 연쇄 실패를 유발함
- `ExecStart=` 변경 시 기존 값을 비우지 않아 unit parse 오류 또는 중복 설정 발생

## Suggested Repo Location

`docs/common/2026-05-20_AM64x_systemd-overlay-dropin.md`

## Suggested Commit Message

```text
docs(common): systemd overlay drop-in 방식 정리
```
