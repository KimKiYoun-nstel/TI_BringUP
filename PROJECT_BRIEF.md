# Project Brief

## 프로젝트 목적

TI AM64x 계열 Evaluation Board(TMDS64EVM, SK-AM64B)를 이용하여 Embedded Linux BSP와 Board Bring-up 역량을 확보한다.

최종 목표는 레퍼런스 보드에서 다음 항목을 충분히 리허설한 뒤, 추후 자체 하드웨어 보드에서 필요한 BSP 포팅과 브링업 절차를 수행할 수 있는 상태가 되는 것이다.

- Boot ROM / SPL / U-Boot / Linux Kernel / Device Tree / RootFS 부팅 흐름 이해
- TI SDK 기반 OS 이미지 빌드 및 부팅
- U-Boot, Kernel, Device Tree 커스터마이징
- Peripheral bring-up 절차 정리
- Pinmux, Clock, Reset, Power, Boot mode 관점의 보드 차이 반영
- 부팅 실패와 디바이스 인식 실패 로그 분석 역량 확보

## 현재 상태

- [ ] 개발 환경 준비
- [ ] TI SDK 확보
- [ ] SD/eMMC 부팅 이미지 준비
- [ ] TMDS64EVM 최초 부팅 확인
- [ ] SK-AM64B 최초 부팅 확인
- [ ] U-Boot 커스터마이징 실습
- [ ] Kernel/Device Tree 커스터마이징 실습
- [ ] Peripheral별 bring-up 체크리스트 작성

## 주요 기준 환경

| 항목 | 값 |
|---|---|
| Host OS | Ubuntu 22.04 WSL 기준 |
| SoC Family | TI AM64x |
| Target Boards | TMDS64EVM, SK-AM64B |
| Build System | TI SDK, Yocto/Buildroot 검토 |
| Debug Interface | UART, JTAG 필요 시 추가 |

## 현재 운영 방식

- ChatGPT Project: 대화, 설명, 분석, 정리 작업 공간
- Git Repo: 장기 보관 지식 저장소
- Markdown 문서: 결정사항, 조사 내용, 작업 로그, 보드별 bring-up 기록

## 범위에 포함

- Embedded Linux BSP
- U-Boot/SPL
- Linux Kernel
- Device Tree
- RootFS
- Peripheral bring-up
- Boot log 분석
- 레퍼런스 보드 기반 자체 보드 준비

## 범위에서 제외 또는 후순위

- MCU bare-metal/RTOS 개발
- 애플리케이션 서비스 개발
- 양산 테스트 자동화
- 회로 설계 자체

## 열린 질문

- [ ] 사용할 TI Processor SDK Linux 버전은?
- [ ] Yocto를 직접 사용할지, TI prebuilt image부터 사용할지?
- [ ] 우선 검증할 peripheral 목록은?
- [ ] 자체 보드에서 레퍼런스 보드와 달라질 가능성이 큰 HW 항목은?
