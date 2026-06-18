# U-Boot DTS Sets

이 디렉터리는 root repo가 직접 관리하는 U-Boot/SPL DTS 자산을 둔다.

구분 원칙:

- reference board용 DTSI 후보 파일은 이 디렉터리 바로 아래 둘 수 있다.
- custom board용 실제 build 입력 DTS는 `custom-board/<board>/sets/<purpose>/` 아래에 둔다.
- workflow 중간물이나 scratch DTS는 두지 않는다.

커스텀 보드에서는 `tools/custom_board_dts_workflow/.../generated/uboot_spl/final/`을 source material로 보고, 실제 build 입력은 이 경로 아래 purpose별 set로 승격해 관리한다.
