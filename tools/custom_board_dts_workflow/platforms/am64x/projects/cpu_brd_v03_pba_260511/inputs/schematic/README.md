# Schematic Inputs

이 디렉터리에는 board 회로도 PDF를 둔다.

권장 규칙:

- 원본 PDF는 수정하지 않는다.
- 파일명에 board명과 revision을 드러낸다.
- 여러 revision이 있으면 실제 분석에 사용한 파일을 `docs/board_dts_decisions.yaml`의 `source_documents`와 맞춘다.

예시:

```text
inputs/schematic/
  CPU_Brd_V03_PBA_260511.pdf
  CPU_Brd_V03_PBA_260511_revnote.pdf
```

이 PDF는 현재 helper가 직접 parse하지 않는다.
대신 다음 작업의 근거로 사용한다.

- board mux 의도 확인
- GPIO/alt function 선택
- external device 주소/목적 확인
- USB/SERDES/Ethernet/MMC 같은 board policy 판단
