# 2026-05-15 SK-AM64B 첫 파이프라인 기반 Kernel+DTB Build/Deploy 부팅 기록

## 작업 목적

이번 작업은 현재 구축 중인 파이프라인을 통해 다음 흐름이 실제로 동작하는지 검증하기 위한 것이다.

```text
workspace kernel build
  -> artifact 수집
  -> SSH 기반 kernel+DTB deploy
  -> reboot
  -> Linux 재기동 확인
```

이 문서는 **첫 파이프라인 기반 kernel+DTB build + deploy + boot 성공 기록**으로 본다.

## 수행 내용

실행된 주요 단계:

```text
1. tools/build/build-kernel.sh 로 artifact 생성
2. tools/install/install-kernel-to-sd.sh 로 /boot/Image 및 /boot/dtb/ti/k3-am642-sk.dtb 반영
3. backup 생성
4. board reboot
5. SSH 복귀 및 boot 결과 검증
```

## 관찰 결과

### 1. bootloader 경로는 유지되었다

이번 로그에서도 bootloader 단계는 기존과 동일하게 SD/MMC 기반 경로를 사용했다.

```text
Trying to boot from MMC2
Loaded env from uEnv.txt
Importing environment from mmc1 ...
```

즉 이번 부팅은 bootloader 실험이 아니라 **kernel image 교체가 중심인 deploy 부팅**이다.

### 2. kernel image load 크기가 커졌다

이전 bootloader deploy 직후 boot 로그에서는 kernel load 크기가 다음과 같았다.

```text
21641728 bytes read
```

이번 파이프라인 기반 kernel deploy 후에는 다음과 같이 증가했다.

```text
42686976 bytes read
```

즉, 약 21.6MB에서 42.7MB로 거의 2배 가까이 증가했다.

### 3. DTB load 크기는 동일했다

이전과 이번 모두 다음 값을 보였다.

```text
63022 bytes read
```

즉 이번 차이는 DTB보다 kernel image 쪽 변화가 핵심이다.

### 4. Linux version 문자열이 바뀌었다

이전:

```text
Linux version 6.18.13-ti-00778-gc21449208550-dirty (oe-user@oe-host) ... Thu Mar 26 20:21:19 UTC 2026
```

이번:

```text
Linux version 6.18.13-gc21449208550 (nstel@KimKiYoun-PC) ... Thu May 14 09:49:02 KST 2026
```

의미:

- `-ti-00778-...-dirty` suffix 제거
- 빌드 사용자/호스트 변경
- 빌드 시각 변경

즉 현재 커널은 TI SDK prebuilt image 계열이 아니라, **로컬 workspace에서 직접 다시 build한 kernel image**가 올라간 상태이다.

## 왜 초기 kernel 로그가 더 커졌는가

현재 repo 기준으로 가장 직접적인 원인은 **kernel build config flow 차이**다.

### 확인된 현재 build flow

`tools/build/build-kernel.sh`는 현재 다음 정책을 사용한다.

```text
Temporary defconfig policy: using make defconfig.
Open question: confirm exact TI SDK defconfig/config fragment for Processor SDK Linux 12 AM64x.
```

즉 현재 파이프라인은 TI SDK가 실제 image 생성에 썼을 가능성이 높은 vendor-pruned 구성 대신, **generic `make defconfig` 기반**으로 kernel을 만들고 있다.

### 현재 `.config`에서 실제로 보이는 generic 기능들

현재 build에 사용된 `.config`에서 다음 generic 기능들이 활성화되어 있음을 확인했다.

```text
CONFIG_9P_FS=y
CONFIG_ACPI=y
CONFIG_E1000=y
CONFIG_E1000E=y
CONFIG_EFI=y
CONFIG_IGB=y
CONFIG_KVM=y
CONFIG_NUMA=y
CONFIG_PCI=y
CONFIG_SERIAL_8250=y
CONFIG_SERIAL_AMBA_PL011=y
```

이런 항목들은 AM64x SK-AM64B 부팅에 꼭 필요한 최소 셋이라기보다, 더 넓은 범용 arm64 환경을 포함하는 일반 구성에 가깝다.

### 로그에서 실제로 늘어난 흔적

이번 로그에는 이전보다 다음과 같은 generic subsystem 초기화가 더 많이 보인다.

예:

```text
NUMA: Faking a node
CONFIG_ACPI 관련 초기화 흔적
KVM 초기화
9p support
e1000 / e1000e / igb / igbvf / sky2 등 추가 네트워크 드라이버 초기화
PL011 / MSM serial 등 추가 serial driver 초기화
```

즉 “소스를 수정하지 않았는데 로그가 늘었다”는 현상은 이상한 것이 아니라,

```text
TI prebuilt / vendor-pruned image 경로
vs
현재 generic defconfig 기반 local rebuild 경로
```

의 차이로 보는 것이 타당하다.

## 검증 결과

deploy 후 reboot 뒤 다음이 확인되었다.

```text
SSH 재접속 성공
uname -a 정상
/proc/cmdline 정상
/boot/Image checksum = local artifact checksum 일치
/boot/dtb/ti/k3-am642-sk.dtb checksum = local artifact checksum 일치
```

즉 이번 부팅은 단순 로그 비교가 아니라,

```text
artifact build -> deploy -> reboot -> running system verification
```

까지 포함하는 실제 파이프라인 검증이다.

## 결론

이번 로그는 **현재 파이프라인을 통한 첫 kernel+DTB build/deploy/boot 성공 로그**로 기록한다.

동시에 다음 open question도 더 명확해졌다.

```text
현재 generic defconfig 기반 kernel은 동작하지만,
TI prebuilt image와 정확히 같은 구성을 재현하려면
TI SDK kernel config flow(defconfig/config fragment/prune flow)를 추가 확인해야 한다.
```

## Follow-up

이후 추가로 확인된 사항:

```text
1. 현재 active kernel/dtb는 golden으로 승격 가능하도록 관리 mode가 추가되었다.
2. DTB-only 실제 deploy 및 reboot 검증이 성공했다.
3. U-Boot prompt에서 SD golden 세트 또는 TFTP를 이용해 복구 부팅할 수 있는 command template 문서가 추가되었다.
4. 현재 repo-build kernel/dtb 세트가 실제 golden baseline으로 승격되었다.
```

## 현재 복구 모델 요약

현재 기준 recovery model은 다음과 같다.

```text
Bootloader 문제:
  OSPI golden bootloader 사용

Kernel/DTB 문제:
  1차 -> SD 내부 golden kernel/dtb 사용
  2차 -> Host PC TFTP kernel/dtb RAM boot 사용

DTB-only 문제:
  active kernel 유지 + golden dtb 또는 TFTP dtb 사용
```

## TFTP Recovery Validation Note

추가로 U-Boot prompt에서 다음 흐름이 실제로 검증되었다.

```text
1. setenv ipaddr / serverip 설정
2. Host PC TFTP root의 golden kernel/DTB 다운로드
3. RAM address에 적재
4. booti로 Linux 진입
5. login prompt 도달
```

즉 현재 recovery model에서 **TFTP 2차 복구 경로는 문서화 수준을 넘어 실제 부팅 성공까지 확인된 상태**로 본다.
