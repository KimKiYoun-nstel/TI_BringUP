# TFTP Root 운영 메모

## 목적

이 디렉터리는 현재 WSL2 host에서 동작 중인 TFTP server의 root directory로 사용한다.

이 경로 아래의 binary payload는 operator가 직접 관리하는 로컬 artifact이며, git의 장기 관리 대상이 아니다.
반면 이 README는 사용 방법과 최근 golden 승격 이력을 남기기 위해 git 관리 대상으로 둔다.

## 현재 golden 파일명 규칙

현재 TFTP recovery의 기본 source는 다음 두 파일이다.

```text
Image.golden
k3-am642-sk.dtb.golden
```

의미:

- `Image.golden` : 현재 repo 기준 마지막으로 의미 있게 정상 동작이 확인된 golden kernel image
- `k3-am642-sk.dtb.golden` : 현재 repo 기준 마지막으로 의미 있게 정상 동작이 확인된 golden dtb

## 현재 사용 방식

U-Boot TFTP recovery command는 이 golden 파일명을 기준으로 작성한다.

예:

```bash
setenv ipaddr 192.168.0.110
setenv serverip 192.168.0.246
setenv bootargs 'console=ttyS2,115200n8 earlycon=ns16550a,mmio32,0x02800000 root=PARTUUID=076c4a2a-02 rw rootfstype=ext4 rootwait'
tftp 0x82000000 Image.golden
tftp 0x88000000 k3-am642-sk.dtb.golden
booti 0x82000000 - 0x88000000
```

## 운영 원칙

1. 이 디렉터리의 binary payload는 git으로 추적하지 않는다.
2. payload 이름은 복구 목적에 맞게 명시적으로 유지한다.
3. golden 승격 시점에 현재 repo의 정상 이미지 세트를 이 디렉터리의 golden 파일명으로 갱신한다.
4. TFTP recovery 실증 로그가 생기면 관련 이력을 아래에 추가한다.

## 최근 golden 승격 이력

### 2026-05-15

현재 repo-build kernel/DTB 세트를 golden 기준으로 사용한다.

기준 artifact:

```text
repo build kernel:  out/kernel/artifacts/Image
repo build dtb:     out/kernel/artifacts/k3-am642-sk.dtb
```

TFTP root 반영 기준 파일명:

```text
Image.golden
k3-am642-sk.dtb.golden
```

관련 검증:

- kernel+DTB deploy 후 reboot/SSH 복귀 검증 완료
- DTB-only deploy 후 reboot/SSH 복귀 검증 완료
- Linux 상태에서 board가 host TFTP root의 golden 파일을 정상 다운로드 가능함을 확인
