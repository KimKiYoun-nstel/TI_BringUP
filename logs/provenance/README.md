# Provenance Log Area

이 디렉터리는 build/deploy 결과가 **어떤 source 상태에서 나왔는지**를 기록한다.

목적:

- workspace 변경이 Main Repo에서 보이지 않는 문제를 막는다.
- SD/OSPI/rootfs에 올라간 결과를 source of truth로 착각하지 않게 한다.
- 리허설 단계의 변경도 나중에 선택적으로 참고할 수 있게 한다.

각 provenance 문서는 최소한 다음을 포함해야 한다.

- Main Repo commit
- workspace path
- workspace baseline commit/tag
- 적용 patch 목록과 hash
- dirty 여부
- build command
- artifact sha256
- deploy 대상(SD/OSPI/rootfs)
- 검증 로그 경로

중요:

- provenance는 "무엇을 빌드했는가"만이 아니라
  "어떤 실험/리허설 상태였는가"를 남기는 문서이다.
- 모든 변경이 최종 custom board output에 누적되는 것이 아니므로,
  provenance는 **선택적 채택 판단 근거**로 남긴다.
