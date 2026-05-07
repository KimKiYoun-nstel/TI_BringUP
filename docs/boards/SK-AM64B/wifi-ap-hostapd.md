# SK-AM64B Wi-Fi AP / hostapd 노트

## 목적

이 문서는 SK-AM64B 기본 Linux 부팅 이후 처음 수행한 Wi-Fi/AP 확인 결과를 기록합니다.

## 초기 증상

가이드에서 기대한 AP:

```text
SSID: AM64xSK-AP
Password: tiwilink8
```

실제로 보인 AP:

```text
SSID: test
```

## 인터페이스 확인

명령:

```bash
ip link
```

관찰:

```text
wlan0 존재
```

해석:

```text
Wi-Fi 네트워크 인터페이스는 생성되어 있음
```

## 드라이버 / 펌웨어 확인

명령:

```bash
dmesg | grep -Ei "wl|wlan|wifi|firmware|mmc0|sdio|cfg80211"
```

중요하게 확인된 로그:

```text
mmc0: new SDIO card at address 0001
wlcore: wl18xx HW: 183x or 180x, PG 2.2
wlcore: loaded
wlcore: PHY firmware version: Rev 8.2.0.0.245
wlcore: firmware booted (Rev 8.9.0.0.86)
```

해석:

```text
SDIO에서 WiLink 모듈이 감지됨
wl18xx/wlcore 드라이버가 로드됨
Wi-Fi 펌웨어 부팅 완료
Wi-Fi 하드웨어 경로는 대체로 정상으로 보임
```

참고:

```text
Direct firmware load for ti-connectivity/wl1271-nvs.bin failed with error -2
```

이 메시지는 보였지만 이후 펌웨어 부팅은 완료되었습니다. AP가 안 보이는 주된 원인이라기보다는 참고 메모로 취급합니다.

## hostapd 상태

명령:

```bash
systemctl status hostapd --no-pager
```

관찰:

```text
hostapd.service loaded
hostapd.service disabled
hostapd.service inactive (dead)
```

해석:

```text
hostapd는 설치되어 있지만 지속적으로 실행되는 systemd 서비스 상태는 아님
```

## hostapd 설정

명령:

```bash
grep -Ei "^(interface|ssid|hw_mode|channel|driver|country_code|wpa|wpa_passphrase)" /etc/hostapd.conf
```

관찰:

```text
interface=wlan0
ssid=test
hw_mode=g
```

해석:

```text
현재 보이는 AP 이름은 /etc/hostapd.conf를 따름
가이드에서 기대한 SSID는 아직 설정되어 있지 않음
```

## 현재 결론

이 문제는 기본적인 Wi-Fi 하드웨어 bring-up 실패로 보이지 않습니다.

현재 상태:

```text
wlan0: 존재
wl18xx 펌웨어: 부팅 완료
hostapd 설정: 존재
AP 가시성: 있음, 이름은 test
```

AP 이름 불일치는 hostapd 설정 문제로 보입니다.

## 보류한 변경

이번 세션에서는 설정을 바꾸지 않습니다.

향후 적용 후보 hostapd 설정:

```conf
interface=wlan0
driver=nl80211
ssid=AM64xSK-AP
hw_mode=g
channel=6
auth_algs=1
wpa=2
wpa_passphrase=tiwilink8
wpa_key_mgmt=WPA-PSK
rsn_pairwise=CCMP
```

## 이후 검증 계획

1. 현재 설정을 백업합니다.

```bash
cp /etc/hostapd.conf /etc/hostapd.conf.bak
```

2. SSID와 비밀번호를 수정합니다.
3. hostapd를 재시작합니다.

```bash
systemctl restart hostapd
systemctl status hostapd --no-pager
```

4. PC/휴대폰에서 AP 접속을 확인합니다.
5. wlan0의 IP를 확인합니다.

```bash
ip addr show wlan0
```

6. 가이드를 따른다면 웹 데모 포트도 확인합니다.

```bash
ss -ltnp | grep 8081
```

## Bring-up 해석

Wi-Fi AP 기능은 여러 계층을 거칩니다.

```text
WiLink 하드웨어
  -> SDIO 감지
  -> wl18xx/wlcore 드라이버
  -> 펌웨어 부팅
  -> wlan0 인터페이스
  -> hostapd AP 모드
  -> IP 주소 / DHCP
  -> 웹 데모 서비스
```

오늘은 최소한 아래 단계까지 확인했습니다.

```text
WiLink 하드웨어 -> 드라이버 -> 펌웨어 -> wlan0 -> 설정된 SSID로 AP 가시화
```
