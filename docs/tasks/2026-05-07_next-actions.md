# 다음 작업 - 2026-05-07 SK-AM64B Bring-up

## 즉시 할 일

### 1. 전체 UART 부팅 로그 저장

권장 경로:

```text
docs/bringup-logs/2026-05-07_SK-AM64B_uart-boot-log.md
```

포함할 내용:

```text
SPL 로그
U-Boot 로그
Kernel 로그
RootFS mount 로그
login prompt
```

### 2. 부팅 메타데이터 수집

보드에서 수집:

```bash
uname -a
cat /proc/cmdline
cat /proc/device-tree/model
fw_printenv 2>/dev/null | head
```

선택 수집:

```bash
dmesg | head -100
dmesg | grep -Ei "machine|model|mmc|root|ext4|firmware|eth|wlan|wlcore"
```

### 3. boot mode 스위치 위치 문서화

보드 사진 또는 텍스트 형태의 스위치 상태를 추가합니다.

권장 대상:

```text
docs/boards/SK-AM64B/README.md
```

또는 신규 문서:

```text
docs/boards/SK-AM64B/boot-mode-switches.md
```

### 4. Wi-Fi AP 가이드 절차 검증

보류한 작업:

```text
hostapd 설정 백업
SSID/비밀번호 수정
hostapd 재시작
PC에서 AP 접속 확인
wlan0 IP 확인
웹 데모 접속 확인
```

### 5. SD 카드 안정성 재확인

이후 부팅 문제가 다시 보이면 아래 경로로 재시도합니다.

```text
다른 SD 카드
다른 SD 카드 리더
Rufus raw write 재실행
Linux dd 기록 경로
```

## 권장 커밋 계획

```bash
git add docs/bringup-logs docs/boards/SK-AM64B docs/common docs/tasks
git commit -m "docs: record SK-AM64B first boot bring-up"
```

## 권장 후속 문서

```text
docs/boards/SK-AM64B/boot-mode-switches.md
docs/bringup-logs/2026-05-07_SK-AM64B_uart-boot-log.md
docs/boards/SK-AM64B/hostapd-ap-setup-result.md
```
