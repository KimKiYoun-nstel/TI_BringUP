# 2026-06-09 SK-AM64B R5F Early Boot Guide Marker Artifact Set

## 목적

이 문서는 future UART uniflash 전에
**TI example 기반 marker를 포함한 명확한 artifact set** 을 준비한 기록이다.

## 왜 이 set을 먼저 만드는가

이전 실험에서는 다음 문제가 있었다.

- source 수정과 runtime 반영 증거를 혼동함
- artifact provenance와 실제 boot 증거가 섞임
- 가설 기반 split-test가 final artifact 반영 실패와 구분되지 않음

따라서 이번 단계에서는 flash하지 않고,
먼저 **proof-oriented artifact set** 을 만드는 데 집중했다.

## 선택 기준

이번 set은 다음 원칙을 따른다.

1. **공식 근거가 명확한 수정만 사용**
   - TI `sbl_ospi_linux` example source가 원래 UART에 출력하는 line에 marker 추가
2. **A53 chain은 이미 local-built fullchain으로 확보된 자산 사용**
3. **split-test variant는 섞지 않음**

즉 이 set은:

- `R5F-silent` 가설 실험 아님
- `A53-only` 가설 실험 아님
- **guide-aligned baseline + explicit SBL runtime proof** 용 set

## 준비 결과

artifact set root:

- `out/r5f-early-boot/image-sets/guide-marker-local-fullchain/`

future uniflash cfg:

- `bsp/mcu-plus/configs/sbl_ospi_linux_sk-am64b_phase2_guide-marker-local-fullchain.cfg`

manifest:

- `out/r5f-early-boot/image-sets/guide-marker-local-fullchain/MANIFEST.md`

## 현재 상태

```text
artifact set built: yes
marker present in SBL build artifact: yes
future uniflash cfg prepared: yes
board flashing performed: no
```
