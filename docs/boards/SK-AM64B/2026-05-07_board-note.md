# SK-AM64B 보드 노트 - 2026-05-07

## 보드 식별 정보

| 항목 | 값 |
|---|---|
| 보드 | TI SK-AM64B |
| 보드 마킹 | PROC100A |
| 목적 | 커스텀 보드 BSP 이식 전에 레퍼런스 보드 bring-up을 리허설하기 위함 |

## 오늘 확인한 내용

```text
65W 어댑터를 사용한 USB-C 전원 입력: OK
정상 동작하는 micro-USB 데이터 케이블을 사용한 J11 디버그 콘솔: OK
CP210x / CP2105 COM 포트 인식: OK
TI 기본 이미지로 microSD 부팅: OK
Linux root 로그인: OK
wlan0 인터페이스 생성: OK
wl18xx 펌웨어 부팅: OK
hostapd 설치 상태: OK
/etc/hostapd.conf 존재 확인: OK
```

## 현재 Wi-Fi/AP 상태

현재 `/etc/hostapd.conf`의 주요 값:

```text
interface=wlan0
ssid=test
hw_mode=g
```

관찰 결과:

- AP는 `test`라는 이름으로 보입니다.
- 가이드에서 기대한 SSID `AM64xSK-AP`는 현재 설정되어 있지 않습니다.
- Wi-Fi 하드웨어 경로 자체는 정상으로 보입니다.

## 보드 Bring-up 해석

BSP/bring-up 관점에서 현재 보드 상태:

```text
전원 레일 / PMIC bring-up: 기본 동작 OK
USB-UART 콘솔 경로: 케이블 교체 후 OK
부팅 미디어 경로: Rufus로 기록한 microSD 기준 OK
부트로더 체인: Linux까지 진입 가능한 수준으로 OK
커널 + Device Tree 경로: eth0, eth1, wlan0 생성 가능한 수준으로 OK
RootFS: root 로그인 및 systemd 서비스 동작 가능한 수준으로 OK
Wi-Fi 주변장치: 드라이버/펌웨어 OK, AP 서비스/설정 후속 확인 필요
```

## 리스크 / 확인 포인트

### SD 카드 기록 신뢰성

Rufus가 성공하기 전까지 Etcher와 Raspberry Pi Imager의 검증이 실패했습니다.

이후 아래와 같은 증상이 보이면 SD 카드나 기록 경로를 먼저 의심합니다.

```text
rootfs 마운트 실패
ext4 파일시스템 오류
부팅 중 간헐적 읽기 오류
손상된 파일로 인한 systemd 서비스 실패
패키지/파일 체크섬 불일치
```

### 전원 공급원

이번 구성에서는 25W USB-C 전원이 충분히 안정적이지 않았습니다.

권장 구성:

```text
65W USB-C PD 노트북 어댑터
가능하면 직접 연결
초기 bring-up 동안 한계가 있는 USB-C 전원은 피하기
```

### UART 케이블

데이터 동기화용으로 표시된 케이블에서는 USB-UART 인식이 되지 않았습니다.

권장 구성:

```text
정상 동작이 확인된 micro-USB 데이터 케이블
J11 DEBUG CONSOLE 포트 사용
부팅 디버깅 전에 Windows Device Manager에서 인식 여부 확인
```

## 다음 보드별 확인 항목

- 부트 모드 스위치 위치를 확인하고 문서화하기
- 전체 UART 부팅 로그 저장하기
- U-Boot 버전 수집하기
- 커널 버전 수집하기
- 부팅 로그에서 DTB / machine model 확인하기
- J11 듀얼 UART 포트의 정확한 COM 포트 매핑 확인하기
- hostapd AP 설정과 웹 데모 접속 여부 확인하기
