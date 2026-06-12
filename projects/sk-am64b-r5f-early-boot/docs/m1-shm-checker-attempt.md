# SK-AM64B M1 SHM Checker Attempt

## 목적

이 문서는 `SK-AM64B R5F early-boot` follow-up의 M1 단계에서

- project 문서화
- R5F firmware / A53 checker build
- SBL OSPI boot 시도
- Linux custom checker로 SHM heartbeat 확인

을 수행한 결과를 남긴다.

중요:

```text
이번 시도는 M1 구현과 수동 검증 경로를 연결하는 데는 성공했지만,
R5F heartbeat SHM runtime closure 자체는 아직 실패 상태다.
```

## 이번 시도에서 추가한 항목

문서:

- `docs/communication-plan.md`
- `docs/m1-shm-checker-attempt.md`
- `README.md` 보강
- `docs/plan.md` 보강
- `docs/gates.md` 보강

Linux checker app:

- `a53/src/main.c`
- `a53/Makefile`

build helper:

- `tools/build/build-r5f-early-boot-app.sh`

## M1 checker 의미

현재 checker는 RPMsg app이 아니라 다음 용도다.

- `/dev/mem` read-only로 `0xA5800000` SHM snapshot read
- `magic/version/abi_size/core` 확인
- `verify` 모드에서 `seq/heartbeat/shm_update_count` 증가 여부 확인

즉 M1 checker는

```text
R5F가 Linux 이전부터 살아 있었고,
Linux 이후에도 SHM heartbeat를 계속 publish 중인가
```

를 보는 최소 진단 app이다.

## local build 결과

### R5F ELF

- path: `out/sk-am64b-r5f-early-boot/am64-main-r5f0_0-fw`
- sha256: `0929be3f9dc6fe887ec6584b45247d2039fab9fb1246a7d8f9e68da3fae03a37`

### A53 checker

- path: `out/sk-am64b-r5f-early-boot/a53/sk_am64b_r5f_early_boot_check`
- sha256: `530d4f79272c60e6135cab8c1790e9b864c6c615e76f4059ff0bd1c67be551cc`

추가 확인:

- `./tools/build/build-r5f-early-boot-app.sh a53` 단독 build 성공
- `./tools/build/build-r5f-early-boot-app.sh all Release` 경로에서도 A53 산출물 재생성 확인

### R5F appimage

최종 regenerate 결과:

- path: `out/sk-am64b-r5f-early-boot/images/r5f-early-heartbeat.mcelf.hs_fs`
- sha256: `3e54f122ba39dff346f857a2ae1636fbb60d40aeec0ad98cb0bf7f5419ccdda7`

## local image generation 이슈

초기 `./tools/build/gen-r5f-multicore-appimage.sh --execute` 실행 시
host 기본 Python 환경의 `pyelftools 0.26` 때문에 다음 계열 오류가 발생했다.

```text
ELFFile.iter_segments() got an unexpected keyword argument 'type'
```

확인 결과:

- MCU+ SDK tool은 `pyelftools==0.31`을 기대한다.
- repo의 SDK tool requirements에도 `pyelftools==0.31`이 명시되어 있다.

우회:

- `/tmp/opencode/mcuplus-py` venv 생성
- `workspace/.../multicore-elf/requirements.txt` install
- 해당 venv 안에서 appimage regenerate 성공

의미:

```text
source 기준 current appimage 생성 자체는 가능했지만,
host 기본 Python 환경은 SDK tool과 그대로 호환되지 않았다.
```

## 추가로 확인된 설정 불일치

M1 검증 후 generated SysConfig 산출물을 다시 확인했을 때,
현재 project 문서/헤더가 기대하는 SHM base와 generated memory model 사이에
의심스러운 불일치가 보였다.

확인된 것:

- project ABI/header 기준 heartbeat SHM base
  - `docs/heartbeat-shm-abi.md` -> `0xA5800000`
  - `r5f/draft/early_heartbeat_status.h` -> `0xA5800000`
- generated SysConfig/linker 기준 shared memory 관련 region
  - `LINUX_IPC_SHM_MEM = 0xA0000000`
  - `USER_SHM_MEM = 0xA5000000`
  - `LOG_SHM_MEM = 0xA5000080`
  - `RTOS_NORTOS_IPC_SHM_MEM = 0xA5004000`
- generated MPU non-cached region도 `0xA0000000` / `0xA5000000` 계열만 직접 다룸
- `r5f/draft/ipc_rpmsg_echo.c`에는 `CacheP_wb` / `CacheP_inv` 같은 cache maintenance 호출이 없다.
- SDK `AddrTranslateP_getLocalAddr()` 구현 기준, mapping region이 없으면 입력 system address를 그대로 local address로 사용한다.

경계 관찰:

- DT inventory 기준 `rtos_ipc_memory_region`
  - base = `0xA5000000`
  - size = `0x00800000`
  - end = `0xA57FFFFF`
- 현재 heartbeat SHM base = `0xA5800000`

즉:

```text
0xA5800000 은 기존 TI IPC carveout의 마지막 주소 다음 위치다.
즉 carveout 내부가 아니라 바로 바깥 경계에 있다.
```

working reference 비교:

- `projects/am64x-r5f-button-event-lab/r5f/example.syscfg`는
  - `0xA5000000` non-cached region 뿐 아니라
  - `0xA5800000` non-cached MPU region도 별도로 둔다.
- 다만 same reference의 shared-memory section placement 자체는
  - `USER_SHM_MEM = 0xA5000000`
  - `LOG_SHM_MEM = 0xA5000080`
  - `RTOS_NORTOS_IPC_SHM_MEM = 0xA5004000`
  쪽을 사용한다.
- 같은 프로젝트 문서 `docs/resource-ownership.md`는
  - `r5f-status-shm@a5800000`
  - DT reserved-memory 선반영
  를 전제로 한다.

반면 현재 early-boot draft는:

- ABI/header는 `0xA5800000`를 기대하지만
- borrowed `example.syscfg`는 `0xA5800000` 전용 MPU/shared-memory region이 없다.

즉 핵심은 다음 쪽에 더 가깝다.

```text
section을 A5800000에 직접 배치하지 않았기 때문이라기보다,
working reference처럼 A5800000용 explicit MPU/non-cached handling과
reserved-memory 모델을 current draft가 갖고 있지 않다.
```

ABI complexity 비교:

- working reference는
  - `seq_begin`
  - field write
  - `seq_end`
  - barrier
  기반 snapshot 일관성 모델을 쓴다.
- current early-boot draft ABI는 intentionally minimal이라
  - `seq_begin/seq_end`
  - barrier 기반 일관성 모델
  을 아직 두지 않는다.

현재 판단:

```text
이번 checker 실패의 직접 원인은
"draft ABI가 reference보다 단순해서" 라기보다,
그 이전 단계인 SHM visibility / address-model / cacheability 문제일 가능성이 더 높다.
```

의미:

```text
현재 draft runtime code는 0xA5800000를 쓰려 하지만,
generated SysConfig/linker는 직접적으로 0xA5800000 user SHM region을 표현하지 않는다.
또한 0xA5800000은 현재 generated non-cached shared-memory region 모델과 직접 맞지 않는다.
그리고 address translation 자체는 기본적으로 입력 주소를 그대로 쓸 가능성이 높다.
특히 0xA5800000은 TI IPC carveout 끝 바로 다음 주소라서,
단순 인접 영역이 아니라 shared-memory 모델 바깥 주소일 가능성이 매우 높다.
working reference는 이 주소를 위해 explicit MPU region과 DT reserved-memory를 같이 맞췄다.
즉 heartbeat SHM base 상수와 current generated memory/cacheability model이 어긋나 있을 가능성이 매우 높다.
```

이 항목은 runtime zero 현상의 강한 원인 후보로 본다.

## board-side 실행 결과

### 1. checker 배포

- board path: `/root/sk_am64b_r5f_early_boot_check`
- SSH copy 및 실행 권한 부여 성공

### 2. 기존 OSPI boot 기준 Linux 재진입

확인된 것:

- Linux SSH 재진입 성공
- checker binary 존재 확인
- `logs/runtime_log` 기준 `r5f-status-shm@a5800000` reserved-memory 생성 확인

추가 확인:

- 마지막 재부팅 기준 `/sys/class/remoteproc/` 관찰에서는
  - `remoteproc0 = 78000000.r5f / attached / unknown`
  - `remoteproc1 = 78200000.r5f / attached / unknown`
  - `remoteproc2 = 5000000.m4fss / running`
  - `remoteproc3 = 78400000.r5f / running`
  - `remoteproc4 = 78600000.r5f / running`

즉 이전 메모에서 자주 언급한 `remoteproc1/2 attached`는
현재 boot session의 index 관찰과 완전히 동일하지 않을 수 있다.
핵심은 index 번호보다 다음 사실이다.

- `78000000.r5f`, `78200000.r5f`는 `attached / unknown`
- 우리가 대상으로 보는 custom early-boot R5F 쪽은 여전히 Linux가 새 firmware를 `running`으로 boot한 형태가 아니다.

### 3. checker 실행 결과

명령:

```bash
/root/sk_am64b_r5f_early_boot_check status
/root/sk_am64b_r5f_early_boot_check verify 300
```

결과:

```text
failed to read a valid SHM snapshot at 0xa5800000
```

raw read 확인:

```text
/bin/devmem2 0xA5800000 w -> 0x00000000
/bin/devmem2 0xA5800004 w -> 0x00000000
/bin/devmem2 0xA5800008 w -> 0x00000000
/bin/devmem2 0xA580000C w -> 0x00000000
```

현재 해석:

```text
Linux 쪽 checker 경로는 동작하지만,
기대한 SHM ABI 값은 board runtime에서 아직 보이지 않는다.
```

## current-source appimage OSPI 반영 시도

TFTP update:

- `tftp/am64x-sbl-ospi-lp4-dualboot-20260612/r5f-early-heartbeat.mcelf.hs_fs`
  를 current-source hash로 교체

U-Boot 시도:

```text
sf probe 0:0
tftp ${loadaddr} am64x-sbl-ospi-lp4-dualboot-20260612/r5f-early-heartbeat.mcelf.hs_fs
sf erase 0x080000 0x40000
sf write ${loadaddr} 0x080000 ${filesize}
```

결과:

- `sf erase` timeout
- `sf write` timeout
- read-back CRC와 source CRC 불일치

의미:

```text
current-source appimage를 0x080000 OSPI slot에 clean하게 반영하지 못했다.
```

다만 이후 reset에서는:

- SBL dual-boot marker 출력
- Linux boot 재진입

까지는 계속 확인되었다.

## 이번 시도에서 확정된 것

1. M1 문서화는 project 내부에 반영되었다.
2. Linux custom SHM checker app은 구현/빌드/보드 실행까지 되었다.
3. current-source R5F appimage regenerate도 host dependency 우회 후 성공했다.
4. board에서 `0xA5800000` SHM은 여전히 valid heartbeat ABI로 관찰되지 않았다.
5. current-source R5F appimage를 OSPI에 clean reflashing 하지는 못했다.

## 현재 판단

현재 상태를 가장 정확히 표현하면 다음과 같다.

```text
M1 implementation: yes
M1 local build path: yes
M1 board checker execution path: yes
M1 runtime heartbeat confirmation: no

Remaining blockers:
1. current-source R5F appimage clean flashing/replay
2. 실제 R5F SHM publish가 왜 0xA5800000에 보이지 않는지 확인
3. `0xA5800000` ABI 기대치와 generated SysConfig/linker shared-memory model 사이의 주소 불일치 확인
```

## 수동 코드/스크립트 리뷰 메모

현재 구현에서 보이는 성격은 다음과 같다.

- `a53/src/main.c`
  - 역할은 명확하고 M1 목적에 맞게 작다.
  - `status` / `verify` 두 모드만 두어 수동 진단용으로는 적절하다.
  - 현재 실패는 checker 자체 문법/실행 문제보다 board runtime SHM visibility 문제로 보는 편이 타당하다.
- `tools/build/build-r5f-early-boot-app.sh`
  - `a53`, `all` 경로 추가는 기능적으로 맞다.
  - Linux devkit `environment-setup`의 `set -u` 충돌을 우회한 점도 현실적이다.

다만 사소한 follow-up 메모는 있다.

1. `build_a53()` 안의 `environment-setup` 경로는 현재 SDK version 문자열이 함수 안에 직접 들어 있다.
   - 현재 repo 환경에서는 충분히 동작하지만, 추후 env 변수 기반으로 정리하면 더 덜 brittle 하다.
2. current draft checker는 minimal ABI용이므로,
   working reference의 `seq_begin/seq_end` snapshot consistency 모델까지는 의도적으로 구현하지 않았다.
   - 이는 현재 M1 범위와는 맞지만, 이후 ABI가 커지면 reader/writer 동시 확장 시점에 재검토가 필요하다.

현재 판단:

```text
이번 턴에서 추가한 코드/스크립트는 전반적으로 M1 목적에 맞고,
지금 실패의 주원인은 checker/build helper보다 runtime SHM side에 있을 가능성이 높다.
```

## 다음 권장 순서

1. OSPI `0x080000` slot write timeout 원인 분리
2. current-source appimage가 실제 boot된다는 증거 확보
3. `early_heartbeat_status.h`의 `0xA5800000`와 generated SysConfig/linker shared-memory region 관계를 먼저 정리
4. 그 상태에서 SHM checker와 raw read를 다시 수행
5. 그래도 zero면 firmware source/runtime 쪽으로 범위를 좁힘

## 후속 수정 및 재검증 결과

이후 다음 수정/반영을 수행했다.

### 적용한 수정

- `projects/sk-am64b-r5f-early-boot/r5f/draft/example.syscfg`
  - `button-event-lab` reference를 따라
  - `0xA5800000`용 explicit non-cached MPU region (`CONFIG_MPU_REGION7`) 추가

### 재생성 artifact

- R5F ELF
  - `out/sk-am64b-r5f-early-boot/am64-main-r5f0_0-fw`
  - sha256: `0929be3f9dc6fe887ec6584b45247d2039fab9fb1246a7d8f9e68da3fae03a37`
- R5F appimage
  - `out/sk-am64b-r5f-early-boot/images/r5f-early-heartbeat.mcelf.hs_fs`
  - sha256: `5b58f8715bfb485ac989380e4ceaa7900ef26743425f07d2ba95803fa432d0ff`

### 보드 반영

- Linux MTD fast path 사용
- `/dev/mtd0` offset `0x80000`
- erase size `0x40000`
- write length `42098`
- readback sha256와 source sha256 일치 확인

### 재부팅 후 M1 결과

checker 실행:

```text
/root/sk_am64b_r5f_early_boot_check status
STATUS: PASS

/root/sk_am64b_r5f_early_boot_check verify 300
STATUS: PASS
seq_delta=4
heartbeat_delta=4
shm_update_count_delta=4
```

raw SHM read:

```text
0xA5800000 -> 0x52354653
0xA5800004 -> 0x00010000
0xA5800008 -> 0x00000024
0xA580000C -> 0x00000152
```

의미:

```text
M1 SHM heartbeat checkpoint는 수정 후 성공했다.
즉 핵심 원인은 checker 자체가 아니라,
current draft의 0xA5800000 SHM 주소와 SysConfig/MPU memory model 정합성 부족이었다.
```

## 최종 판정

현재 상태를 최종적으로 표현하면 다음과 같다.

```text
M1 implementation: yes
M1 board verification: yes
M1 SHM heartbeat confirmation: yes

Confirmed fix:
  add explicit non-cached MPU handling for 0xA5800000
  + clean reflashing of current-source appimage
```
