# Templates

이 디렉터리는 SoC별 profile과 분리된 공용 템플릿을 둔다.

현재 제공 템플릿:

- `ti_board_project/`

의도:

- `platforms/<soc>/` 아래에는 SoC profile과 실제 board project만 둔다.
- 새 board project 시작용 뼈대는 `templates/` 아래에 둔다.
- 이 템플릿을 복사한 뒤 실제 위치는 `platforms/<soc>/projects/<board-project>/`가 된다.
