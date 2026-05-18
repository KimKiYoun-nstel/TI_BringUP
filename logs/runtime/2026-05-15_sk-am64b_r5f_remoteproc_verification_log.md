# SK-AM64B R5F remoteproc / RPMsg 검증 로그

- 날짜: 2026-05-15
- 대상 보드: SK-AM64B
- 상태: 정상 검증 완료
- 권장 저장 위치: `logs/runtime/2026-05-15_sk-am64b_r5f_remoteproc_verification_log.md`
- 관련 이슈 문서: `docs/bringup-logs/2026-05-15_sk-am64b_r5f_remoteproc_rpmsg_resolution.md`

## 목적

R5F remoteproc 및 RPMsg userspace service 이슈가 실제 보드에서 해결되었는지 확인하기 위한 runtime 증적을 선별 보관한다.

## Kernel / module sync

```text
===== kernel/module sync =====
uname -r: 6.18.13-gc21449208550
drwxr-xr-x 3 weston tracing 4096 May 15 08:11 /lib/modules/6.18.13-gc21449208550
```

판정:

- 실행 중인 kernel release와 `/lib/modules/$(uname -r)`가 일치한다.
- 이전의 kernel Image / module tree mismatch 문제는 재현되지 않았다.

## Loaded modules

```text
===== loaded modules =====
rpmsg_ctrl             12288  0
rpmsg_char             20480  1 rpmsg_ctrl
ti_k3_r5_remoteproc    24576  0
ti_k3_m4_remoteproc    12288  0
ti_k3_common           20480  2 ti_k3_r5_remoteproc,ti_k3_m4_remoteproc
mux_ti_k3_event        12288  0
```

판정:

- R5F/M4F remoteproc driver가 로드되었다.
- RPMsg userspace character device 생성을 위한 `rpmsg_char`, `rpmsg_ctrl`도 로드되었다.

## remoteproc sysfs

주요 remoteproc entry:

```text
remoteproc0 -> 5000000.m4fss
remoteproc1 -> 78000000.r5f
remoteproc2 -> 78200000.r5f
remoteproc3 -> 78400000.r5f
remoteproc4 -> 78600000.r5f
```

추가 remoteproc entry:

```text
remoteproc5  -> 3000a000.txpru
remoteproc6  -> 30034000.pru
remoteproc7  -> 30038000.pru
remoteproc8  -> 30004000.rtu
remoteproc9  -> 30006000.rtu
remoteproc10 -> 3000c000.txpru
remoteproc11 -> 300b4000.pru
remoteproc12 -> 30084000.rtu
remoteproc13 -> 3008a000.txpru
remoteproc14 -> 300b8000.pru
remoteproc15 -> 30086000.rtu
remoteproc16 -> 3008c000.txpru
```

판정:

- `/sys/class/remoteproc/`가 비어 있지 않다.
- M4F, R5F, PRU/RTU/TXPRU remoteproc device들이 등록되어 있다.

## remoteproc states

```text
5000000.m4fss      running    am64-mcu-m4f0_0-fw
78000000.r5f       running    am64-main-r5f0_0-fw
78200000.r5f       running    am64-main-r5f0_1-fw
78400000.r5f       running    am64-main-r5f1_0-fw
78600000.r5f       running    am64-main-r5f1_1-fw
```

PRU 계열은 현재 offline:

```text
3000a000.txpru     offline
30034000.pru       offline
30038000.pru       offline
30004000.rtu       offline
30006000.rtu       offline
...
```

판정:

- M4F 1개와 R5F 4개는 모두 `running`이다.
- PRU 계열 offline은 이번 이슈 범위 밖이다.

## RPMsg device nodes

```text
/dev/rpmsg0
/dev/rpmsg1
/dev/rpmsg2
/dev/rpmsg3
/dev/rpmsg4
/dev/rpmsg_ctrl0
/dev/rpmsg_ctrl1
/dev/rpmsg_ctrl2
/dev/rpmsg_ctrl3
/dev/rpmsg_ctrl4
```

판정:

- RPMsg character device와 control device가 정상 생성되었다.
- userspace에서 RPMsg endpoint를 생성하고 통신할 수 있는 상태다.

## rpmsg_json.service

```text
===== rpmsg_json service =====
active
* rpmsg_json.service
     Loaded: loaded (/usr/lib/systemd/system/rpmsg_json.service; enabled; preset: enabled)
    Drop-In: /etc/systemd/system/rpmsg_json.service.d
             `-override.conf
     Active: active (running) since Mon 2026-05-18 01:32:23 UTC; 2min 28s ago
    Process: 7565 ExecStartPre=/bin/sh -c for i in $(seq 1 30); do [ -e /sys/bus/platform/devices/78000000.r5f/remoteproc/remoteproc1/state ] && [ "$(cat /sys/bus/platform/devices/78000000.r5f/remoteproc/remoteproc1/state 2>/dev/null)" = "running" ] && [ -e /dev/rpmsg_ctrl1 ] && exit 0; sleep 1; done; exit 1 (code=exited, status=0/SUCCESS)
   Main PID: 7570 (rpmsg_json)
```

판정:

- `override.conf` drop-in이 실제 적용되었다.
- `ExecStartPre` 대기 조건이 성공했다.
- `rpmsg_json.service`가 `active (running)` 상태다.

## rpmsg_json round-trip 로그

```text
Read 2009 bytes from /usr/share/benchmark-server/app/oob_data.json
Avg round trip time: 1309 usecs
Avg round trip time: 540 usecs
Avg round trip time: 1601 usecs
Avg round trip time: 219 usecs
Total 2009 bytes have output
Write 2009 bytes to oob_update.json
```

추가 관측:

```text
Avg round trip time: 825 usecs
Avg round trip time: 449 usecs
Avg round trip time: 229 usecs
Avg round trip time: 225 usecs
Total 2009 bytes have output
Write 2009 bytes to oob_update.json
```

판정:

- A53 Linux userspace와 R5F firmware 사이 RPMsg 왕복 통신이 실제로 수행되었다.
- 결과 파일 `oob_update.json` write까지 확인되었다.

## Kernel log 핵심 시퀀스

M4F:

```text
k3-m4-rproc 5000000.m4fss: assigned reserved memory node memory@a4000000
k3-m4-rproc 5000000.m4fss: configured M4F for remoteproc mode
remoteproc remoteproc0: 5000000.m4fss is available
remoteproc remoteproc0: Booting fw image am64-mcu-m4f0_0-fw
virtio_rpmsg_bus virtio0: rpmsg host is online
remoteproc remoteproc0: remote processor 5000000.m4fss is now up
```

R5F0_0:

```text
platform 78000000.r5f: configured R5F for remoteproc mode
platform 78000000.r5f: assigned reserved memory node memory@a0000000
remoteproc remoteproc1: 78000000.r5f is available
remoteproc remoteproc1: Booting fw image am64-main-r5f0_0-fw
virtio_rpmsg_bus virtio1: rpmsg host is online
remoteproc remoteproc1: remote processor 78000000.r5f is now up
```

R5F0_1:

```text
platform 78200000.r5f: configured R5F for remoteproc mode
platform 78200000.r5f: assigned reserved memory node memory@a1000000
remoteproc remoteproc2: 78200000.r5f is available
remoteproc remoteproc2: Booting fw image am64-main-r5f0_1-fw
virtio_rpmsg_bus virtio2: rpmsg host is online
remoteproc remoteproc2: remote processor 78200000.r5f is now up
```

R5F1_0:

```text
platform 78400000.r5f: configured R5F for remoteproc mode
platform 78400000.r5f: assigned reserved memory node memory@a2000000
remoteproc remoteproc3: 78400000.r5f is available
remoteproc remoteproc3: Booting fw image am64-main-r5f1_0-fw
virtio_rpmsg_bus virtio3: rpmsg host is online
remoteproc remoteproc3: remote processor 78400000.r5f is now up
```

R5F1_1:

```text
platform 78600000.r5f: configured R5F for remoteproc mode
platform 78600000.r5f: assigned reserved memory node memory@a3000000
remoteproc remoteproc4: 78600000.r5f is available
remoteproc remoteproc4: Booting fw image am64-main-r5f1_1-fw
virtio_rpmsg_bus virtio4: rpmsg host is online
remoteproc remoteproc4: remote processor 78600000.r5f is now up
```

## 현재 이슈와 무관한 로그

아래 로그는 현재 R5F/RPMsg 해결 판정에는 직접 영향이 없다.

```text
check access for rdinit=/init failed: -2, ignoring
platform led-controller: deferred probe pending: leds-gpio: Failed to get GPIO '/led-controller/led-0'
wl18xx_driver wl18xx.5.auto: Direct firmware load for ti-connectivity/wl1271-nvs.bin failed with error -2
```

분류:

- `rdinit=/init failed`: 현재 systemd 부팅이 완료되었으므로 치명 이슈로 보지 않는다.
- `led-controller deferred probe`: LED GPIO/DT 관련 별도 이슈 후보.
- `wl1271-nvs.bin failed`: Wi-Fi NVS firmware 별도 이슈 후보.

## 최종 판정

```text
R5F remoteproc bring-up: PASS
M4F remoteproc bring-up: PASS
RPMsg kernel path: PASS
/dev/rpmsg* 생성: PASS
rpmsg_json.service startup ordering: PASS
a53 userspace <-> r5f firmware RPMsg round-trip: PASS
```

따라서 이번 R5F remoteproc / RPMsg 이슈는 live board 기준 해결 완료로 판정한다.
