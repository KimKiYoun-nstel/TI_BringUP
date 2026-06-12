# 2026-06-09 SK-AM64B A53-only Corrected Artifact

## 핵심 결론

이 문서는 이전 A53-only 실험이 왜 신뢰할 수 없었는지와,
어떻게 corrected artifact set을 다시 준비했는지를 기록한다.

## 이전 실패의 직접 원인

이전 A53-only source 수정은 존재했지만,
final artifact 반영에는 실패했다.

직접 원인:

- `main.c` 의 `bootConfig` unused variable
- `-Werror` 로 인해 build 중단

즉 이전 failure는 boot 결과 이전에
**artifact generation failure + stale artifact 사용 가능성** 이었다.

## corrected rebuild 조치

1. `bootConfig` unused variable 제거
2. `generated/`, `obj/`, `.out`, `.bin`, `.tiimage` 삭제
3. clean rebuild 강제
4. final artifact 문자열 재검증

## corrected evidence

- source에는 `Starting linux-only application` 가 존재한다.
- corrected clean rebuild 후 final artifact에도 `Starting linux-only application` 가 존재한다.

즉 이제부터는 적어도
**A53-only 의도는 final SBL artifact까지 반영된 상태** 라고 말할 수 있다.

## 준비 결과

artifact set root:

- `out/r5f-early-boot/image-sets/a53-only-optee-verbose/`

future cfg:

- `bsp/mcu-plus/configs/sbl_ospi_linux_sk-am64b_phase2_a53-only-optee-verbose-fixed.cfg`
