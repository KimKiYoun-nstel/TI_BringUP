# AM64x TSN C Case C4 Remoteproc Loadability Check

## 목적

`gptp_icssg_switch` / `gptp_icssg_dualmac` build 산출물이 TMDS64EVM Linux `remoteproc` 경로에 바로 올라갈 수 있는지 정적 관점에서 먼저 판단한다.

## 분석 대상

### candidate firmware

- `gptp_icssg_switch.release.out`
- `gptp_icssg_dualmac.release.out`

### 비교 기준 firmware

- 현재 TMDS에서 실제 `remoteproc1 (78000000.r5f)`로 올라가는 firmware:
  - `/lib/firmware/am64-main-r5f0_0-fw`

### 관련 Linux reserved-memory

TMDS DTS 기준:

```text
main_r5fss0_core0_dma_memory_region = 0xa0000000 size 0x00100000
main_r5fss0_core0_memory_region     = 0xa0100000 size 0x00f00000
```

## 핵심 결론

```text
example build success           = yes
raw ELF artifact exists         = yes (.out)
Linux remoteproc drop-in ready  = no (current evidence)
```

가장 큰 차이는 다음 두 가지다.

1. `gptp_icssg_*`는 현재 `MSRAM 0x7008xxxx / 0x701xxxx` 중심 메모리 배치를 사용한다.
2. 현재 Linux `remoteproc`로 동작 중인 firmware는 `0xa0100000` carveout 중심이며 `.resource_table`을 포함한다.

## 1. gptp_icssg_switch 결과

### section header 핵심

- `.vectors` = `0x00000000`
- `.text` = `0x70080000`
- `.rodata` = `0x700c0be0`
- `.bss` = `0x700d9c80`
- `.data` = `0x701624c0`
- `.text.hwi` 등 나머지 실행 코드 = `0x70167400` 근처
- `.resource_table` 없음

### program header 핵심

LOAD segment:

- `0x00000000`
- `0x70080000`
- `0x700d9c80`
- `0x701624c0`
- `0x70167400`
- `0x70168730`

### linker map 핵심

- memory config:
  - `MSRAM origin=0x70080000 length=0x0017c000`
- 모든 주요 code/data/bss가 `MSRAM` 안에 배치됨

## 2. gptp_icssg_dualmac 결과

### section header 핵심

- `.vectors` = `0x00000000`
- `.text` = `0x70080000`
- `.rodata` = `0x700c0cc0`
- `.bss` = `0x700d8a80`
- `.data` = `0x70170200`
- `.text.hwi` 등 나머지 실행 코드 = `0x70175a80` 근처
- `.resource_table` 없음

### program header 핵심

LOAD segment:

- `0x00000000`
- `0x70080000`
- `0x700d8a80`
- `0x70170200`
- `0x70175a80`
- `0x70176db0`

### memory config 특징

- switch와 마찬가지로 `MSRAM` 중심 배치
- `.resource_table` 없음

## 3. 현재 working remoteproc firmware와 비교

TMDS에서 실제 동작 중인 `am64-main-r5f0_0-fw`는 다음 특징을 가진다.

### section header 핵심

- `.vectors` = `0x00000000`
- `.resource_table` = `0xa0100000`
- `.bss` = `0xa0101000`
- `.text` = `0xa010fd80`
- `.rodata` = `0xa0119ff0`
- `.data` = `0xa011aa60`

### program header 핵심

LOAD segment:

- `0x00000000`
- `0xa0100000` (`.resource_table`)
- `0xa0101000` (`.bss/.sysmem/.stack`)
- `0xa010fd80` (`.text/.rodata`)
- `0xa011aa60` (`.data`)
- `0xa011af08` (stack sections)

### 의미

- 현재 working firmware는 Linux DTS의 `main_r5fss0_core0_memory_region = 0xa0100000 + 15 MiB`와 정합성이 높다.
- 반면 `gptp_icssg_*`는 `0x7008xxxx / 0x701xxxx`를 사용하므로 현재 remoteproc carveout 모델과 바로 맞지 않는다.

## 4. resource_table 관점

### 확인된 사실

- `gptp_icssg_switch.release.out`: `.resource_table` 없음
- `gptp_icssg_dualmac.release.out`: `.resource_table` 없음
- `am64-main-r5f0_0-fw`: `.resource_table` 존재

### 해석

- `resource_table` 부재가 곧바로 `remoteproc absolutely impossible`을 뜻하는 것은 아니다.
- 하지만 **현재 TMDS Linux가 실제로 올리고 있는 R5 firmware 관례와는 다르다.**
- 특히 `rpmsg`, `trace`, carveout 기술이 필요한 경로라면 추가 작업 가능성이 높다.

## 5. artifact format 관점

### 확인된 사실

- `gptp_icssg_*` build는 `.out`와 `.mcelf.hs_fs`를 모두 만든다.
- `.mcelf.hs_fs`는 MCU+ SDK boot image 계열 산출물이다.

### 해석

- Linux `remoteproc` 입력 후보는 `.mcelf.hs_fs`가 아니라 **raw ELF인 `.out`** 쪽이다.
- 다만 현재 `.out` 자체가 Linux remoteproc 메모리 모델과 다르므로, format보다 **link address / section layout**이 더 큰 문제다.

## 6. 현재 단계의 판단

### 확정

- C0/C3 관점에서 example build 자체는 성공한다.
- `.out` 산출물은 존재한다.
- 하지만 현재 `.out`은 `TMDS Linux remoteproc`에 바로 넣는 drop-in firmware로 보기 어렵다.

### 가장 가능성 높은 blocker

1. `MSRAM 0x7008xxxx / 0x701xxxx` 중심 메모리 배치
2. Linux current carveout (`0xa0100000`)와의 비정합
3. `.resource_table` 부재로 인한 remoteproc convention mismatch

## 7. 현실적인 adaptation 경로

현재 기준으로 가장 현실적인 경로는 다음 둘 중 하나다.

### 경로 A. gptp_icssg example을 Linux remoteproc memory model로 재링크

- `example.syscfg` / linker / generated files를 조정해
- code/data/bss/resource_table을 `0xa0100000` carveout 기준으로 재배치
- 필요 시 `.resource_table` 추가

### 경로 B. Linux remoteproc-enabled R5 example scaffold에 gptp ICSSG app를 이식

- 예: `ipc_rpmsg_echo_linux` 계열의 Linux remoteproc-ready 구조를 기준으로
- ICSSG gPTP app logic만 옮기기

현재 판단으로는 **경로 B가 더 안전할 가능성**이 있다.

이유:

- 이미 Linux remoteproc와 메모리 배치가 맞는 scaffold를 재사용할 수 있음
- C4에서 memory/resource_table 문제를 한 번에 줄일 수 있음

## 8. 다음 액션

1. `gptp_icssg_switch.release.map` 기준으로 memory/section 재배치 포인트 정리
2. `ipc_rpmsg_echo_linux`의 `.resource_table` / syscfg 메모리 섹션 구조와 비교
3. 어떤 경로(A/B)로 갈지 결정
4. 그 다음에야 첫 `remoteproc firmware load` 시도를 하는 것이 안전함

## 현재 판정

- C4 정적 분석: 완료
- C4 runtime load 시도: 아직 안 하는 편이 합리적
- 이유: 지금 형태 그대로는 실패 가능성이 높고, 실패 원인도 이미 정적으로 상당 부분 드러남
