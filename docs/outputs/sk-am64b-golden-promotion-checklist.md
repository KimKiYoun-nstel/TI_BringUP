# SK-AM64B Golden 승격 체크리스트

## 목적

이 문서는 `promote-golden` 실행 전에, 현재 active kernel/DTB 이미지를 정말로 golden 기준본으로 승격해도 되는지 판단하기 위한 체크리스트이다.

중요 원칙:

```text
deploy 성공 = golden 승격 아님
실제 부팅 및 의미 있는 동작 검증 완료 = golden 승격 후보
최종 승인 = 사용자 판단
```

## 적용 대상

현재 기준 golden 관리 대상:

```text
/boot/Image
/boot/dtb/ti/k3-am642-sk.dtb
```

승격 대상 golden 경로:

```text
/boot/Image.golden
/boot/dtb/ti/k3-am642-sk.dtb.golden
```

## 1. 기본 생존성 체크

다음 항목이 모두 만족해야 한다.

- [ ] U-Boot까지 정상 진입
- [ ] Linux kernel panic 없이 userspace 진입
- [ ] rootfs mount 성공
- [ ] serial console 또는 SSH 중 최소 1개 진입 가능

확인 예:

```bash
uname -a
cat /proc/cmdline
cat /proc/device-tree/model
```

## 2. 현재 active artifact 일치성 체크

다음 항목이 모두 만족해야 한다.

- [ ] `/boot/Image`가 의도한 deploy 대상과 일치
- [ ] `/boot/dtb/ti/k3-am642-sk.dtb`가 의도한 deploy 대상과 일치
- [ ] deploy 후 checksum 검증 통과

확인 예:

```bash
sha256sum /boot/Image /boot/dtb/ti/k3-am642-sk.dtb
sha256sum out/kernel/artifacts/Image out/kernel/artifacts/k3-am642-sk.dtb
```

## 3. 보드 기본 기능 체크

다음 항목은 최소 기준으로 확인하는 것이 좋다.

- [ ] `Machine model` 또는 `/proc/device-tree/model`이 기대 보드와 일치
- [ ] `console=ttyS2,115200n8` 등 핵심 bootargs 유지
- [ ] Ethernet 링크 또는 SSH 진입 가능
- [ ] DTB 변경 의도와 관련된 probe 결과 확인

확인 예:

```bash
cat /proc/device-tree/model
cat /proc/cmdline
ip addr
dmesg | grep -Ei 'mmc|ethernet|phy|usb|i2c|firmware'
```

## 4. 실험 목적별 추가 체크

### Kernel + DTB 실험

- [ ] 새 kernel image로 실제 reboot 성공
- [ ] driver probe / 서비스 기동이 기대와 크게 다르지 않음
- [ ] 이전 golden과 비교했을 때 치명적인 회귀가 없음

### DTB-only 실험

- [ ] active kernel 유지 상태로 reboot 성공
- [ ] DTB 변경 의도가 실제로 반영되었는지 확인
- [ ] 실패 시 golden DTB로 되돌릴 수 있는 상태인지 확인

## 5. recovery readiness 체크

golden 승격 전에도 다음이 준비되어 있어야 한다.

- [ ] OSPI known-good bootloader 존재 확인
- [ ] boot mode switch 변경 절차 인지
- [ ] U-Boot SD golden 복구 command template 확인
- [ ] U-Boot TFTP recovery command template 확인

## 6. 추천 검증 절차

현재 repo에서는 다음 helper script를 사용할 수 있다.

```bash
./tools/install/verify-kernel-dtb-postdeploy.sh 192.168.0.110 all
./tools/install/verify-kernel-dtb-postdeploy.sh 192.168.0.110 dtb-only
```

이 스크립트는 SSH 복귀, `/boot` 파일 checksum, bootargs, model 등의 기본 확인을 자동화한다.

## 7. 최종 승인 기준

다음이 모두 만족하면 `promote-golden` 실행 후보로 본다.

- [ ] 기술적 체크 통과
- [ ] 실험 목적상 의미 있는 정상 동작 확인
- [ ] 사용자 승인 완료

승격 실행 예:

```bash
./tools/install/install-kernel-to-sd.sh 192.168.0.110 promote-golden
```

## 8. 한 줄 요약

```text
golden은 “최근 deploy 결과물”이 아니라,
실제 부팅과 의미 있는 동작 검증까지 끝난 마지막 정상 기준본이다.
```
