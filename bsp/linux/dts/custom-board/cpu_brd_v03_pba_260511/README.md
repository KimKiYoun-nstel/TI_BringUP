# CPU_BRD_V03_PBA_260511 Linux DTS Sets

이 디렉터리는 `cpu_brd_v03_pba_260511` 커스텀 보드의 Linux용 root-managed DTS set를 둔다.

원칙:

- `tools/custom_board_dts_workflow/.../generated/linux/final/`은 board reference이자 source material이다.
- 실제 build에 쓰는 DTS는 이 디렉터리 아래 `sets/<purpose>/`로 승격해서 관리한다.
- 시험용 set는 두지 않는다. 실제 target에 의미 있는 정책이 반영된 set만 둔다.
