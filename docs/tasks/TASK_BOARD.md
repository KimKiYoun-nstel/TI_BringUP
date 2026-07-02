# Task Board

## 현재

- [ ] UART 단일 MCP + target(`sk`/`tmds`/`custom`) 운용을 실제 새 세션에서 재검증
- [ ] TMDS64EVM C Case 후속 검증: forwarding/gPTP end-to-end 검증과 반복 reboot 회귀 확인
- [ ] TMDS64EVM C Case 후속 안정화: RM ownership fix 이후 MDIO probe 정합성과 `.icss_mem/.enet_dma_mem` donor parity 필요성 재검토
- [x] SK-AM64B SBL OSPI Linux LPDDR4 reginit delta를 workspace-base asset/note로 정리
- [x] SK-AM64B SBL OSPI Linux 기본 dual-boot 경로 OSPI write 및 Linux boot 재검증
- [ ] SK-AM64B SBL OSPI Linux dual boot 이후 Linux attach / RPMsg 검증
- [ ] RootFS overlay build/deploy skeleton 정리
- [ ] TI prebuilt kernel config flow 확인
- [ ] rpmsg_json.service startup ordering race 완화책 장기 정책 검토
- [ ] SK-AM64B direct USB root pre-root enumeration 원인 분리 (`dr_mode=host` vs initramfs holdoff)

## 다음

- [ ] RootFS-only deploy loop 설계 및 검증
- [ ] U-Boot FDT fixup 관찰 절차 정리
- [ ] boot-flow 변경 이력 관리 규칙 정착
- [ ] TMDS64EVM C Case temporary U-Boot override를 장기 boot path로 승격할지 결정

## 이후

- [ ] extlinux 또는 EFI slot strategy 필요성 재평가
- [ ] Kernel defconfig 확정
- [ ] Device Tree 구조 분석
- [ ] Peripheral별 bring-up checklist 작성
- [ ] 자체 보드 포팅 차이점 체크리스트 작성

## 완료

- [x] UART daemon/client/MCP를 target profile 기반 TCP 기본 경로와 단일 generic MCP 구조로 정리
- [x] TMDS64EVM C Case C0 example inventory 작성
- [x] TMDS64EVM C Case C1 baseline Linux 상태 수집
- [x] TMDS64EVM C Case C1 dualmac overlay 기반 eth1/eth2 ICSSG dual-port Linux 검증
- [x] TMDS64EVM C Case C2 ownership 분리 overlay 초안 작성 및 compile 확인
- [x] TMDS64EVM C Case C2 ownership 분리 live boot 시뮬레이션 검증
- [x] TMDS64EVM C Case C4 정적 remoteproc loadability 분석
- [x] TMDS64EVM C Case C4 adaptation 경로 결정 (`remoteproc-ready scaffold 이식`)
- [x] TMDS64EVM C Case C4 Path B skeleton source integration 및 remoteproc-friendly ELF link
- [x] TMDS64EVM C Case C5 boot-time remoteproc firmware override 실검증
- [x] TMDS64EVM C Case C5 ICSSG_1 PKTDMA RM ownership fix로 Path B `EnetUdma_openRxCh` blocker 해소 및 gPTP task start 확인
- [x] TMDS64EVM TSN C Case 1차 정리: patch/provenance 자산 승격과 성공 범위 고정
- [x] R5F early boot task-unit-1 inventory 문서화 및 repo skeleton 정리
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
- [x] SK-AM64B Phase 4 SHM status block live board 검증
- [x] SK-AM64B Phase 4 VTM temperature telemetry live board 검증
- [x] SK-AM64B SBL OSPI Linux LPDDR4 reginit 기반 A53-only first boot 성공
- [x] SK-AM64B SBL OSPI Linux LPDDR4 dual-boot OSPI boot 성공
