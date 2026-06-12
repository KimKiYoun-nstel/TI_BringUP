# TI ARM CLANG Projectspec Draft Note

현재 canonical R5F project들의 CCS projectspec은 모두 다음 3개 입력을 copy 한다.

```text
../ipc_rpmsg_echo.c
../main.c
../example.syscfg
```

따라서 early-boot heartbeat용 projectspec을 새로 만들더라도
최소 입력 구조는 동일하게 유지하는 편이 자연스럽다.

현재 단계에서는 `example.projectspec` 초안을 추가했다.

의미:

- canonical MCU+ CCS project 구조와 같은 3+1 file 입력(`main.c`, `ipc_rpmsg_echo.c`, `example.syscfg`, `early_heartbeat_status.h`)을 사용한다.
- 아직 board-validated project는 아니지만, buildable draft로 승격하기 위한 첫 단계다.
- source selection 기준은 계속 `../README.md`와 `../../docs/heartbeat-source-selection.md`를 따른다.
