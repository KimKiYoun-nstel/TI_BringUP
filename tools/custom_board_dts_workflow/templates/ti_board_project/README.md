# TI Board Project Template

이 디렉터리는 TI SoC 기반 새 custom board project를 시작할 때 복사해서 쓰는 base 템플릿이다.

사용 방법:

1. 이 디렉터리를 `platforms/<soc>/projects/<board-project>/`로 복사한다.
2. `inputs/netlist/`, `inputs/schematic/`에 실제 입력 파일을 넣는다.
3. `docs/board_dts_decisions.yaml`을 실제 board 판단으로 채운다.
4. `config/paths.local.yaml.example`를 `config/paths.local.yaml`로 복사한 뒤 `board_project_dir`와 `netlist_path`를 맞춘다.
5. Stage-1을 실행한다.

이 템플릿은 입력 구조와 문서 뼈대만 제공한다.
`generated/`와 `reports/`는 실행 후 채워진다.
