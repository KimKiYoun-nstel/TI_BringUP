# DTS Delivery Set

이 디렉터리는 `cpu_brd_v03_pba_260511` 보드의 전달용 DTS 세트만 따로 모은다.

대상:

- 워크플로우를 모르는 사람
- 순수하게 DTS/DTSI 파일을 받아서 정책을 반영해 재편집할 사람

포함 원칙:

- 사람이 직접 읽고 편집할 DTS/DTSI
- 왜 이런 구성을 선택했는지 설명하는 handoff notes

제외 원칙:

- workflow 입력 파일
- `board_dts_decisions.yaml`
- `reports/`
- 스크립트/템플릿/설정 파일

구성:

- `linux/`
- `uboot_spl/`
