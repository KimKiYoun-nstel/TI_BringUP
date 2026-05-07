# Windows에서 SK-AM64B UART 콘솔 연결

## 목적

이 문서는 첫 번째 SK-AM64B 부팅 세션에서 확인한 UART 콘솔 설정과 트러블슈팅 결과를 기록합니다.

## 보드 포트

관련 포트:

```text
USB-C:
  보드 전원 입력

J11 micro-USB:
  DEBUG CONSOLE
  CP2105 USB-to-UART 브리지
  COM 포트로 인식되어야 함

J12 micro-USB:
  XDS110/JTAG 관련 디버그 포트
```

일반적인 Linux 부팅 콘솔 작업에는 아래 포트를 사용합니다.

```text
J11 DEBUG CONSOLE
```

## 핵심 교훈

COM 포트 인식은 SD 카드 부팅과 별개입니다.

```text
SD 카드가 없어도:
  부팅 로그는 안 나올 수 있음

정상적인 데이터 케이블로 J11이 연결되어 있으면:
  Windows는 USB-UART 장치를 인식해야 함
```

## 문제: COM 포트가 보이지 않음

증상:

```text
J11 연결됨
Windows Device Manager 변화 없음
COM 포트 없음
알 수 없는 USB 장치 없음
CP210x/CP2105 장치 없음
```

초기 의심 대상:

```text
잘못된 포트 연결
드라이버 문제
USB 허브 문제
보드 문제
케이블 문제
```

최종 원인:

```text
micro-USB 케이블 문제
```

해결:

```text
다른 micro-USB 케이블로 교체함
즉시 COM 포트가 나타남
```

## 트러블슈팅 체크리스트

COM 포트가 보이지 않으면:

1. 케이블이 USB-C 전원 포트가 아니라 J11에 연결되었는지 확인합니다.
2. Windows Device Manager를 띄워 둡니다.
3. 케이블을 분리/재연결하면서 장치가 나타나거나 사라지는지 확인합니다.
4. 아래 항목을 확인합니다.
   Ports (COM & LPT)
   Universal Serial Bus controllers
   Other devices
5. 정상 동작이 확인된 다른 micro-USB 데이터 케이블을 사용합니다.
6. USB 허브만 쓰지 말고 PC의 직접 포트에도 연결해 봅니다.
7. USB 인식이 확인되거나 최소한 알 수 없는 장치가 보일 때만 Silicon Labs CP210x VCP 드라이버 재설치를 고려합니다.

## 예상 장치 이름

Windows에서 보일 수 있는 이름:

```text
Silicon Labs CP210x USB to UART Bridge
Silicon Labs CP2105 Dual USB to UART Bridge
Enhanced COM Port
Standard COM Port
```

COM 포트가 두 개 보이면 Linux 콘솔은 두 번째로 인식된 포트에 있을 수 있습니다.

## 터미널 설정

Tera Term, PuTTY 또는 유사한 시리얼 터미널을 사용합니다.

일반적인 설정:

```text
Baudrate: 115200
Data bits: 8
Parity: None
Stop bits: 1
Flow control: None
```

## Bring-up 해석

UART 콘솔 사용 가능 여부는 보드 bring-up의 첫 관문 중 하나입니다.

```text
COM 포트 자체가 인식되지 않음:
  USB 케이블 / USB-UART 브리지 / 커넥터 / PC 문제

COM 포트는 열리지만 로그가 없음:
  전원 / 부트 모드 / 부팅 매체 / SoC 부팅 문제

SPL 로그가 보임:
  Boot ROM과 초기 부팅 이미지 경로까지 도달

U-Boot가 보임:
  DDR 초기화와 부트로더 handoff가 통과했을 가능성 높음

커널 로그가 보임:
  Linux 이미지와 DTB 경로까지 도달

로그인 프롬프트가 보임:
  RootFS와 userspace까지 도달
```
