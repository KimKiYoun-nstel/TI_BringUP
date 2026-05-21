# 이슈 및 주의사항

## 회로도 세부사항 주의

초기 planning note에는 `R342`, `C349`가 언급되어 있었지만, 이후 로컬 schematic 확인에서는 SW1 debounce network가 `R318 4.7K`, `C338 0.1uF`로 보였다. 따라서 정확한 SK-AM64B 설계 자료와 보드 revision으로 교차 검증되기 전까지는 component reference와 값은 해당 board design package 전용 정보로 취급해야 한다.

## GPIO Interrupt 소유권

Linux가 SW1 net의 main-domain 쪽을 gpio-keys 또는 다른 input 경로로 노출할 수 있다. 이것이 곧바로 R5F의 `MCU_GPIO0_6` 읽기를 막는다는 뜻은 아니지만, production-safe 동작을 주장하려면 ownership과 pinmux 상태를 반드시 검증해야 한다.

## 이벤트 전달 모델

`button monitor`는 하나의 RPMsg endpoint를 지속적으로 열어두고 subscribe한다. firmware는 가장 최근 subscriber endpoint를 기억하고, task context에서 이벤트 텍스트를 전송한다. subscriber가 없어도 이벤트 count는 계속 증가하며 `button status`에서 확인할 수 있다.

## 프로젝트 밖에 유지하는 관련 문서

이번 Phase 2에서 파생된 다음 문서는 프로젝트 로컬 문서가 아니라 상위 `docs/`에 유지한다.

- `docs/boards/SK-AM64B/2026-05-21_SK-AM64B_phase2-sw1-r5f-gpio-irq-sysfw-rm.md`
  - 이유: SK-AM64B 특정 보드 이슈와 진행 경과를 다룸
- `docs/common/2026-05-21_AM64x_sysfw-rm-resource-ownership.md`
  - 이유: 다른 보드/다른 interrupt ownership 문제에도 재사용 가능한 공통 개념 문서임
- `docs/setup/2026-05-21_AM64x_tiboot3-sysfw-rm-rebuild.md`
  - 이유: 특정 프로젝트를 넘어서 boot chain 재구성 절차를 설명하는 setup 문서임
