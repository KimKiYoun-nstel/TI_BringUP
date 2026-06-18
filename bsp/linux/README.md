# Linux BSP Area

이 디렉터리는 `workspace/ti-linux-kernel-sdk12`에서 승격한 AM64x Linux patch, config, DTS 자산, 노트를 관리한다.

원칙:

- full Linux source tree는 이 repo에 넣지 않는다.
- `dts/` 아래의 custom board DTS set는 root repo가 실제 build 입력으로 소유하는 자산이다.
- workflow 내부 `tools/custom_board_dts_workflow/.../generated/*/final/`은 board reference이자 source material이고, build 입력 자체는 아니다.
