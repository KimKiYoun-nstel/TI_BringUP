# Research Notes

조사/학습한 내용을 장기 재사용 가능한 형태로 기록합니다.

## 작성 규칙

- 자료에서 확인한 사실과 내 판단을 분리합니다.
- 출처가 있으면 링크 또는 파일명을 남깁니다.
- 보드 브링업 관점의 재사용 포인트를 반드시 남깁니다.

---

## R-001. AM64x Embedded Linux 부팅 흐름 기본 구조

- 날짜: 2026-04-30
- 상태: Draft
- 질문:
  - AM64x 보드에서 Linux가 올라오기까지 어떤 단계가 있는가?
- 요약:
  - Boot ROM이 boot mode 설정에 따라 초기 boot media를 선택한다.
  - SPL이 DDR, clock, pinmux 등 초기 하드웨어 설정을 수행한다.
  - U-Boot proper가 kernel image, device tree, rootfs 로딩을 담당한다.
  - Linux Kernel은 device tree를 기반으로 peripheral driver를 probe한다.
  - RootFS가 mount되고 init/systemd가 사용자 공간을 시작한다.
- BSP/Bring-up 관점:
  - 부팅 실패 위치를 단계별로 나누어 봐야 한다.
  - UART 로그가 어느 단계까지 나오는지가 첫 번째 분기점이다.
- 확인 필요:
  - 현재 사용할 TI Processor SDK Linux 버전의 boot image 구성
  - TMDS64EVM/SK-AM64B의 boot switch 설정
