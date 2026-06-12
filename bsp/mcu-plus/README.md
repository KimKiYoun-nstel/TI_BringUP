# MCU+ SDK BSP Area

이 디렉터리는 AM64x MCU+ SDK 관련 **장기 보관 대상 변경**만 관리한다.

원칙:

- 외부 SDK 원본 `~/ti/am64x/mcu_plus_sdk_*`는 reference-only 이다.
- 직접 수정은 금지한다.
- 재현이 필요한 SDK-level 변경은 patch 또는 재현 절차로 이 디렉터리에 반입한다.
- 단순 실험 결과는 여기로 바로 누적하지 않고, 먼저 `docs/research/`와 `logs/provenance/`에서 근거를 남긴다.
- bulk generated asset가 root-cause fix 자체인 경우에는 `bsp/mcu-plus/syscfg/` 아래 standalone asset로 둘 수 있다.

이 디렉터리의 목적은 **최종 제품 baseline 누적**이 아니라,
**리허설/실험 이력 중 나중에 선택적으로 채택 가능한 변경 자산**을 보관하는 것이다.
