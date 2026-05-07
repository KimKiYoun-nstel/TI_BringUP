# 2026-05-07 SK-AM64B First SD Boot

## Summary

SK-AM64B / PROC100A 보드에서 TI Processor SDK Linux 기본 이미지를 microSD로 부팅하여 root shell 진입까지 확인했다.

이번 기록은 전체 UART boot log 원문을 포함하지 않는다. UART boot log는 별도 파일로 추가할 예정이다.

## Environment

| Item | Value |
|---|---|
| Board | TI SK-AM64B |
| Board marking | PROC100A |
| Boot media | microSD |
| Image source file | `tisdk-default-image-am64xx-evm-12.00.00.07.04.rootfs.wic.xz` |
| Final write method | `.wic.xz` 압축 해제 후 Rufus로 `.wic` raw write |
| Console | J11 DEBUG CONSOLE micro-USB |
| Login result | `root@am64xx-evm:~#` prompt reached |

## Bring-up Result

최초 SD boot 실습 결과, 다음 단계까지 정상 진행되었다.

```text
Power ON
  -> Boot ROM
  -> SPL
  -> U-Boot
  -> Linux Kernel
  -> RootFS mount
  -> root login prompt
```

성공 기준:

- UART console 확보
- Linux boot 진행 확인
- root shell 진입 확인

## Issues Encountered

### 1. USB-UART COM port not detected

초기 증상:

```text
J11 micro-USB 연결 후 Windows 장치관리자에 아무 변화 없음
COM port 없음
Unknown device도 없음
```

원인:

```text
micro-USB cable issue
```

해결:

```text
다른 micro-USB 케이블로 교체 후 Windows에서 COM port 즉시 인식
```

판단:

- 보드, CP2105, Windows driver 문제가 아니었다.
- 포장에 data sync가 표기된 케이블도 실제 환경에서는 불량 또는 접점 문제 가능성이 있다.

### 2. Power instability with 25W USB-C supply

초기 상태:

```text
25W USB-C 전원 사용 시 보드 전원 상태가 안정적이지 않음
```

해결:

```text
65W 노트북용 USB-C 전원 어댑터 사용
```

판단:

- SK-AM64B 초기 bring-up에서는 여유 있는 USB-C PD 전원을 사용하는 것이 좋다.
- 이후 전원 관련 이상 증상이 나오면 power source와 cable을 우선 확인한다.

### 3. SD card image write failure

초기 방법:

```text
balenaEtcher로 .wic.xz 직접 write
Raspberry Pi Imager로 .wic.xz 직접 write
```

증상:

```text
balenaEtcher:
  writer process ended unexpectedly

Raspberry Pi Imager:
  write 후 verify 99~100% 근처에서 오류 발생
```

해결 방법:

```text
1. .wic.xz 압축 해제
2. .wic raw image 생성
3. Rufus로 .wic image write
4. 보드 부팅 성공
```

판단:

- boot partition 일부 파일이 Windows에서 보이는 것만으로 write 성공을 판단하면 안 된다.
- validation 실패가 있으면 rootfs 후반부 손상 가능성이 있다.
- 이번에는 Rufus raw write 결과로 부팅과 root login까지 성공했다.

## Verification Commands Used After Boot

```bash
ip link
dmesg | grep -Ei "wl|wlan|wifi|firmware|mmc0|sdio|cfg80211"
systemctl --type=service --state=running | grep -Ei "hostapd|wifi|wlan|network|connman|demo|docker"
systemctl status hostapd --no-pager
grep -Ei "^(interface|ssid|hw_mode|channel|driver|country_code|wpa|wpa_passphrase)" /etc/hostapd.conf
```

## Wi-Fi Initial Observation

`wlan0` 인터페이스는 생성되었다.

확인된 의미:

```text
WiLink module SDIO detection OK
wl18xx/wlcore driver load OK
firmware boot OK
wlan0 creation OK
```

AP 이름은 가이드의 `AM64xSK-AP`가 아니라 `test`로 보였다.

확인된 설정:

```text
interface=wlan0
ssid=test
hw_mode=g
```

판단:

- Wi-Fi hardware bring-up 자체는 정상에 가깝다.
- AP SSID 불일치는 `/etc/hostapd.conf` 설정 문제로 판단한다.
- hostapd 설정 변경은 다음 작업으로 미룬다.

## Follow-up

- 전체 UART boot log를 별도 파일로 저장한다.
- hostapd 설정을 가이드 기준으로 수정하고 AP 접속 및 web demo 동작을 확인한다.
- SD 카드 write 절차와 UART cable troubleshooting을 reusable note로 분리한다.
