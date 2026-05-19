# SK-AM64B 보드 적용 및 검증 절차

## 목적

repo 안에서 관리되는 RPMsg 테스트 프로젝트를 실제 SK-AM64B 보드에 올리고,

- Host에서 테스트 자산 배포
- 보드 내부에서 활성 firmware 전환
- A53 단발성 테스트 클라이언트 실행
- RPMsg payload 왕복 검증
- 원래 benchmark baseline 복구

를 반복 가능한 절차로 정리한다.

## 사전 조건

1. 보드 SSH 접속 가능
   - 예: `root@192.168.0.110`
2. 설치된 SDK/툴체인 준비
3. `rpmsg_json.service` 하드닝 override가 이름 기반으로 수정된 상태
4. 현재 보드 baseline이 정상인지 확인

```bash
ssh root@192.168.0.110 "systemctl is-active benchmark_server.service; systemctl is-active rpmsg_json.service"
```

기대 결과:

- `benchmark_server.service`: `active`
- `rpmsg_json.service`: `active`

## 1. 프로젝트 빌드

```bash
./tools/build/build-sk-am64b-rpmsg-test.sh all
```

생성물:

- R5F ELF
  - `out/sk-am64b-rpmsg-test/ccs_projects/sk_am64b_rpmsg_test_r5fss0_0_freertos_ti_arm_clang/Release/sk_am64b_rpmsg_test_r5fss0_0_freertos_ti_arm_clang.out`
- R5F deploy alias
  - `out/sk-am64b-rpmsg-test/am64-main-r5f0_0-fw`
- A53 userspace 테스트 클라이언트
  - `out/sk-am64b-rpmsg-test/a53/sk_am64b_rpmsg_test_a53`

## 2. Host에서 보드로 파일 배포

```bash
./tools/install/deploy-sk-am64b-rpmsg-host.sh 192.168.0.110
```

이 단계는 보드에 다음 파일을 복사한다.

1. 테스트 firmware
   - `/usr/lib/firmware/ti-bringup/sk-am64b-rpmsg-test/am64-main-r5f0_0-fw`
2. A53 테스트 클라이언트
   - `/usr/local/bin/sk_am64b_rpmsg_test_a53`
3. 보드 내부 적용/복구 스크립트
   - `/usr/local/sbin/sk-am64b-rpmsg-manage.sh`

이 단계에서는 **활성 firmware 링크를 바꾸지 않는다.**

## 3. 보드 내부 적용

보드에서 직접 또는 SSH로 다음 명령을 실행한다.

```bash
/usr/local/sbin/sk-am64b-rpmsg-manage.sh apply auto
```

이 스크립트는:

1. 현재 활성 firmware target을 저장한다.
2. `benchmark_server.service`, `rpmsg_json.service`를 중지한다.
3. `/usr/lib/firmware/am64-main-r5f0_0-fw` symlink를 테스트 firmware로 전환한다.
4. 보드를 재부팅한다.

현재 운영 모델에서는 **runtime stop/start는 사용하지 않고, 적용은 reboot 기반으로만 수행한다.**

## 4. A53 테스트 클라이언트 실행

```bash
/usr/local/bin/sk_am64b_rpmsg_test_a53 payload-from-a53
```

이 프로그램은 service가 아니라 **단발 실행형 테스트 클라이언트**다.

동작:

1. `libti_rpmsg_char`로 `R5F_MAIN0_0`에 연결한다.
2. RPMsg payload를 1회 전송한다.
3. R5F firmware의 echo 응답을 수신한다.
4. 결과를 출력하고 종료한다.

## 5. 성공 판정

성공 시 출력 예시는 다음과 같다.

```text
TX: payload-from-a53
RX: payload-from-a53
STATUS: PASS
```

의미:

- A53가 보낸 문자열을 R5F firmware가 그대로 echo했다.
- 양쪽 payload가 byte-for-byte 일치했다.

## 6. 수동 확인 포인트

### 6-1. 새 R5F firmware가 실제로 로드됐는지

```bash
ssh root@192.168.0.110 "journalctl -b --no-pager | grep -n 'am64-main-r5f0_0-fw' | tail -20"
```

테스트 firmware 적용 시에는 boot log에 새 firmware 크기가 찍힌다.

### 6-2. RPMsg 채널 생성 여부

```bash
ssh root@192.168.0.110 "journalctl -b --no-pager | grep -n 'rpmsg_chrdev' | tail -40"
```

### 6-3. 현재 활성 firmware 링크 확인

```bash
ssh root@192.168.0.110 "readlink -f /usr/lib/firmware/am64-main-r5f0_0-fw"
```

기대 결과:

- 테스트 적용 상태:
  - `/usr/lib/firmware/ti-bringup/sk-am64b-rpmsg-test/am64-main-r5f0_0-fw`
- baseline 복구 상태:
  - `/usr/lib/firmware/mcusdk-benchmark_demo/am64-main-r5f0_0-fw`

### 6-4. baseline 복구 여부

```bash
ssh root@192.168.0.110 "ls -l /usr/lib/firmware/mcusdk-benchmark_demo/am64-main-r5f0_0-fw; systemctl is-active benchmark_server.service; systemctl is-active rpmsg_json.service"
```

기대 결과:

- firmware 크기: `86352`
- `benchmark_server.service`: `active`
- `rpmsg_json.service`: `active`

## 7. 보드 내부 복구

baseline으로 되돌릴 때는 다음 명령을 사용한다.

```bash
/usr/local/sbin/sk-am64b-rpmsg-manage.sh restore
```

이 스크립트는:

1. 원래 저장해 둔 baseline target으로 symlink를 되돌린다.
2. benchmark baseline 서비스들을 다시 시작한다.
3. 보드를 재부팅한다.

현재 운영 모델에서는 **복구도 reboot 기반으로만 수행한다.**

## 8. 실패 시 확인 순서

1. `journalctl -b --no-pager | grep -n 'remoteproc\|rpmsg'`
2. `ls -l /sys/class/remoteproc`
3. `ls -l /dev/rpmsg* /dev/rpmsg_ctrl*`
4. `systemctl status benchmark_server.service --no-pager`
5. `systemctl status rpmsg_json.service --no-pager`

## 9. 기존 benchmark 서비스와의 관계

다음 서비스는 이번 프로젝트와 별도인 benchmark baseline용 Linux 서비스다.

- `benchmark_server.service`
- `rpmsg_json.service`

이번 프로젝트는 이 서비스들을 대체하지 않는다.
다만 benchmark baseline도 `rpmsg_chrdev` 기반 RPMsg 채널을 사용하므로, 테스트 firmware를 적용할 때는 채널/endpoint 점유 충돌을 피하기 위해 관련 서비스를 중지한다.
