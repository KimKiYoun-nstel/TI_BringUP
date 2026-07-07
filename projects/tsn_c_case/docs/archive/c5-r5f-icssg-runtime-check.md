# AM64x TSN C Case C5 R5F ICSSG Runtime Check

## 목적

Path B에서 만든 `remoteproc-friendly ICSSG gPTP ELF`를 실제 TMDS64EVM에 올려, Linux `remoteproc`가 firmware를 부팅하는지와 trace/log가 어디까지 나오는지 확인한다.

## 시험 전 안전 조치

### 기존 firmware 백업

TMDS 보드 안에서 기존 firmware를 먼저 백업했다.

```text
/root/case_backups/am64-main-r5f0_0-fw.backup-2026-07-01
```

SHA256 확인 결과 original과 backup은 동일했다.

### 시험용 firmware 배치

host에서 다음 test ELF를 TMDS에 복사했다.

```text
/lib/firmware/gptp_icssg_linux_remoteproc_r5f0_0_test.out
```

## runtime stop/start 직접 교체 시도 결과

현재 running firmware를 Linux runtime에서 바로 바꿔 보려 했으나 실패했다.

### 대상

```text
/sys/class/remoteproc/remoteproc1
name = 78000000.r5f
firmware = am64-main-r5f0_0-fw
```

### 결과

`echo stop > state` 시도에서:

```text
platform 78000000.r5f: notify_shutdown_rproc: timeout waiting for rproc completion event
remoteproc remoteproc1: can't stop rproc: -16
write error: Device or resource busy
```

### 해석

- 현재 기본 firmware는 runtime stop에 협조하지 않는다.
- 따라서 live swap 방식보다 `boot-time firmware-name override`가 더 안전하다.

## boot-time temporary override 방식

U-Boot에서 base DT를 로드한 뒤 다음 두 종류의 변경을 일시 적용했다.

### 1. C2 ownership 유지

- `cpsw port2` disable
- `mdio_mux_1` disable
- `icssg1-eth` disable

### 2. firmware-name override

```text
/bus@f4000/r5fss@78000000/r5f@78000000
  firmware-name = "gptp_icssg_linux_remoteproc_r5f0_0_test.out"
```

`saveenv`는 하지 않았다.

## boot 결과

Linux 부팅은 성공했고 serial login prompt까지 도달했다.

### remoteproc 상태

boot 후 확인 결과:

```text
remoteproc0
  name     = 78000000.r5f
  state    = running
  firmware = gptp_icssg_linux_remoteproc_r5f0_0_test.out
```

즉 **Linux remoteproc가 새 test ELF를 실제로 읽고 running 상태로 전환하는 것까지는 성공**했다.

### netdev 상태

```text
eth0 only
eth1/eth2 absent
```

즉 C2 ownership 제거 상태도 유지되었다.

## trace 결과

### remoteproc trace

```text
[unknown]     0.000000s : [RPROC_TRACE] stage=boot state=enter code=0 main start
```

### 의미

- 우리가 추가한 trace macro는 실제로 remoteproc trace 경로에 도달했다.
- 최소한 firmware entry와 trace plumbing은 동작했다.

## 관찰된 한계

현재 trace에는 다음 한 줄만 보였다.

```text
stage=boot state=enter code=0 main start
```

즉 다음 trace는 보이지 않았다.

- `system and board init complete`
- `main task created`
- `remoteproc scaffold entry`
- `driver init start`
- `peripherals=...`

### 현재 해석

- firmware는 entry까지는 진입한다.
- 그러나 `System_init()` / `Board_init()` / 혹은 그 직후 초기 단계에서 더 진행하지 못하고 있을 가능성이 높다.
- 최소한 현재 trace 기준으로는 `EnetApp_mainTask()`까지 정상 진입했다고 보긴 어렵다.

## dmesg 관찰

### 확인된 사실

- Linux는 다음을 출력했다.

```text
remoteproc remoteproc0: Booting fw image gptp_icssg_linux_remoteproc_r5f0_0_test.out, size 4651320
remoteproc remoteproc0: remote processor 78000000.r5f is now up
```

- 별도의 immediate crash/oops/panic는 보이지 않았다.

### 해석

- Linux 관점에서는 remoteproc bring-up 자체는 성공으로 보인다.
- 하지만 firmware 내부 진행 상태는 trace 기준으로 초반에서 멈춘다.

## 원복

시험 후 정상 reboot로 원복했다.

원복 확인:

```text
remoteproc0 firmware = am64-main-r5f0_0-fw
```

또한 test ELF는 삭제했다.

```text
/lib/firmware/gptp_icssg_linux_remoteproc_r5f0_0_test.out  -> removed
```

backup 파일은 유지했다.

## 현재 판정

### 성공한 것

1. backup 절차 확보
2. Linux remoteproc가 Path B test ELF를 실제로 load 가능
3. remoteproc trace 경로로 custom status log가 실제 노출됨
4. C2 ownership 제거 상태와 결합한 boot-time 실검증 성공

### 아직 실패/미완료인 것

1. firmware가 `main start` 이후 더 진행하지 못함
2. `enet init`, `icssg init`, `phy link`, `gptp state` trace는 아직 확보 못함

## 다음 디버깅 포인트

1. `main.c`에서 `System_init()` / `Board_init()` 전후 trace를 더 세분화
2. `Drivers_open()` 이전 단계에서 어디까지 살아 있는지 확인
3. scaffold syscfg와 ICSSG syscfg 병합으로 인해 생긴 초기화 부작용 여부 분리
4. 필요 시 `Board_init()` 대신 더 작은 초기화 subset으로 줄여 첫 bring-up point를 찾기
