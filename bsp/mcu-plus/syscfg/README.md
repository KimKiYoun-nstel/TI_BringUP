# MCU+ SysCfg Area

이 디렉터리는 R5F early boot rehearsal에 필요한
MCU+ SDK SysConfig 관련 repo-managed 자산을 보관한다.

원칙:

- SDK 예제 전체 복사는 하지 않는다.
- 우리 프로젝트가 직접 관리해야 하는 최소 `.syscfg` delta 또는 참고 사본만 둔다.
- local workspace에서 검증되기 전까지는 여기에 실험 산출물을 무분별하게 누적하지 않는다.
- 장기 보관 가치가 없는 generated file은 두지 않는다.

예상 사용처:

- early-boot heartbeat firmware용 최소 syscfg
- RPMsg/resource-table용 syscfg diff 근거
- SBL OSPI Linux용 board-specific config memo
- standalone LPDDR4 `board_ddrReginit.h` asset
