# Task Board

## 현재

- [ ] RootFS overlay build/deploy skeleton 정리
- [ ] TI prebuilt kernel config flow 확인
- [ ] rpmsg_json.service startup ordering race 완화책 장기 정책 검토

## 다음

- [ ] RootFS-only deploy loop 설계 및 검증
- [ ] U-Boot FDT fixup 관찰 절차 정리
- [ ] boot-flow 변경 이력 관리 규칙 정착

## 이후

- [ ] extlinux 또는 EFI slot strategy 필요성 재평가
- [ ] Kernel defconfig 확정
- [ ] Device Tree 구조 분석
- [ ] Peripheral별 bring-up checklist 작성
- [ ] 자체 보드 포팅 차이점 체크리스트 작성

## 완료

- [x] Ubuntu 22.04 WSL 준비
- [x] `TI_BringUP` GitHub repo 생성
- [x] Git 기반 프로젝트 지식 저장소 운영 방식 결정
- [x] TI SDK source workspace와 patch 기반 repo 운영 정책 확정
- [x] Bootloader build pipeline 구현
- [x] Kernel build pipeline 구현
- [x] SK-AM64B boot-flow BASE와 Option A deploy strategy 문서화
- [x] Bootloader 실제 deploy 및 reboot 검증
- [x] Kernel+DTB 실제 deploy 및 reboot 검증
- [x] DTB-only 실제 deploy 및 reboot 검증
- [x] curated logs under `logs/` tracking policy 정리
- [x] U-Boot SD golden / TFTP recovery command template 문서화
- [x] U-Boot TFTP recovery 실제 boot 검증
- [x] AM64x remoteproc empty sysfs 현상 live board 재검증 및 정상 boot 상태 확인
- [x] rpmsg_json.service startup ordering race 완화책 적용 및 reboot 검증
