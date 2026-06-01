# SK-AM64B USB Boot Experiment Cycle

## 목적

이 문서는 SK-AM64B USB boot 실험을 매번 같은 방식으로 수행하기 위한 **단일 실험 사이클 표준 절차**를 정의한다.

핵심 원칙은 다음과 같다.

1. 한 번의 실험은 준비부터 결과 분석까지 하나의 cycle로 끝나야 한다.
2. `logs/runtime_log`가 항상 최종 UART truth다.
3. `booti` 직전 U-Boot watchdog 240초를 반드시 설정한다.
4. 실험 중 hang/pending이 발생하면 watchdog reset까지 관찰한다.
5. watchdog reset 없이 pending이 유지되면, 사용자의 수동 reboot 요청으로 해당 cycle을 종료한다.

## 실험 1회 정의

한 번의 실험은 반드시 아래 4단계로 구성한다.

1. 실험 준비
2. 실험 진행
3. 실험 모니터링
4. 결과 분석 및 다음 실험 준비

이 4단계를 모두 끝내야 그 실험이 종료된 것이다.

---

## 1. 실험 준비

이 단계에서 먼저 다음을 확정한다.

### 1.1 실험 ID와 목적

- 이번 실험이 무엇을 검증하는지 한 줄로 적는다.
- 이전 실험과 무엇이 다른지 명시한다.
- 성공 기준과 실패 기준을 먼저 적는다.

예:

```text
N17: initramfs holdoff로 pre-root USB mass-storage readiness를 직접 관찰한다.
```

### 1.2 실험 시료 확정

다음을 실험 전에 고정한다.

- kernel Image
- DTB
- initramfs 유무와 파일명
- root selector
- bootargs
- U-Boot 입력 command sequence
- watchdog 설정값

실험 시료는 바뀌면 다른 실험이다.

즉, `booti` 직전까지 사용되는 모든 입력 자산을 먼저 확정해야 한다.

### 1.3 보드 baseline 확인

실험 시작 전 보드가 최소한 다음 중 하나의 정상 상태에 있어야 한다.

- Linux root shell
- `login:` prompt
- U-Boot prompt

확인 기준:

- Linux shell: `# `
- login prompt: `login:`
- U-Boot prompt: `=> `

### 1.4 로그 기준점 확보

실험 시작 전 `logs/runtime_log`에서 현재 상태를 확인한다.

필요하면 실험 시작 시각과 실험명을 메모에 기록한다.

---

## 2. 실험 진행

### 2.1 실험용 시료 생성

필요한 경우에만 다음을 수행한다.

- DTB rebuild
- initramfs 생성
- boot partition/U-Boot load 대상 파일 갱신
- `uEnv.txt` rehearsal override 준비

이 단계는 **실험 시작 전** 끝나 있어야 한다.

### 2.2 보드 상태 파악 후 U-Boot 진입

현재 보드 상태를 먼저 파악한다.

- shell이면 reboot -> autoboot stop -> U-Boot 진입
- login이면 login 가능 여부를 먼저 판단
- 이미 U-Boot면 바로 다음 단계 진행

reboot -> U-Boot 진입은 항상 UART 기준으로 수행한다.

### 2.3 U-Boot에서 실험 command 입력

다음을 순서대로 입력한다.

1. 실험용 bootargs 설정
2. kernel load
3. DTB load
4. initramfs load (필요 시)
5. loaded DTB / bootargs sanity check
6. watchdog 240 설정
7. `booti`

중요:

- `saveenv`는 하지 않는다.
- watchdog은 **항상 `booti` 직전**에 건다.
- watchdog command는 repo에서 확인된 `wdt` sub-system 기준으로 수행한다.

권장 watchdog sequence 예:

```text
wdt list
wdt dev watchdog@e000000
wdt start 240000
```

실제 board에서 device 선택이 다르면 그 cycle에서 사용한 device name을 같이 기록한다.

---

## 3. 실험 모니터링

`booti` 이후에는 다음 중 어디에 해당하는지 watchdog timeout 전까지 판단한다.

1. 정상 부팅 성공
2. diagnostic initramfs 성공 진입
3. pending / root wait / hang
4. kernel panic / oops / reset loop
5. watchdog timeout 후 SoC reset

### 3.1 성공 판정

실험 목적에 따라 성공 판정이 다르다.

- 일반 root boot 실험이면 `login:` 또는 shell 도달
- `init=/bin/sh` 실험이면 `Run /bin/sh as init process`
- initramfs 진단 실험이면 diag marker 출력과 목표 로그 수집 성공

### 3.2 실패 판정

다음 중 하나면 그 cycle은 실패다.

- watchdog timeout 후 reset 확인
- panic/oops 후 정상 목적 미달성
- expected USB block device 미생성
- root mount 미완료

### 3.3 pending 상태 규칙

pending 상태는 다음처럼 취급한다.

1. UART 로그를 계속 본다.
2. watchdog reset이 일어나면 자동으로 실패 확정이다.
3. watchdog reset 없이 장시간 멈추면 사용자가 수동 reboot을 수행한다.
4. 이 경우 agent는 수동 reboot 요청 후 그 cycle을 종료한다.

즉, pending 상태에서 다음 실험으로 넘어가면 안 된다.

---

## 4. 결과 분석 및 다음 실험 준비

### 4.1 결과 정리

한 cycle 종료 후 반드시 다음을 정리한다.

- 사용한 실험 시료
- U-Boot command sequence
- watchdog 사용 여부와 설정값
- `booti` 이후 핵심 UART evidence
- 성공/실패 판정
- root cause 가설

### 4.2 실패 시 분석 기준

특히 실패한 경우 다음을 분리한다.

1. U-Boot load 실패
2. kernel handoff 실패
3. host probe 실패
4. storage enumeration 실패
5. root mount 실패
6. userspace/initramfs 이후 문제

### 4.3 다음 실험으로 넘어가는 조건

다음 실험은 아래가 끝난 뒤에만 시작한다.

- 이전 cycle 판정 완료
- UART evidence 확보 완료
- 실험 시료 차이점 정의 완료
- board recovery 상태 확인 완료

---

## 운영 체크리스트

### A. 실험 전

- [ ] 이번 실험 ID/목적 정의
- [ ] 성공/실패 기준 정의
- [ ] kernel/DTB/initramfs/root selector 확정
- [ ] watchdog command sequence 확정
- [ ] 현재 board state 확인

### B. 실험 중

- [ ] U-Boot prompt 진입
- [ ] bootargs 입력
- [ ] load command 입력
- [ ] watchdog 240 설정
- [ ] `booti` 실행
- [ ] UART 로그 모니터링

### C. 실험 후

- [ ] 성공/실패 판정
- [ ] watchdog reset 여부 확인
- [ ] 핵심 UART line 추출
- [ ] 결과 문서 갱신
- [ ] 다음 실험 가설 정의

---

## N17에 대한 적용 규칙

N17은 다음으로 정의한다.

```text
목적: initramfs holdoff로 pre-root USB mass-storage readiness를 직접 관찰한다.
성공: initramfs diag가 시작되고, root device 출현 여부를 watchdog timeout 전까지 로그로 남긴다.
실패: diag 미진입, panic, 또는 watchdog reset 전까지 root device readiness 증적 확보 실패.
```

주의:

- N17은 단순 "부팅 성공" 실험이 아니라 **원인 분리용 진단 실험**이다.
- 따라서 initramfs 진입과 diag logging 자체도 중요한 성공 조건이다.
