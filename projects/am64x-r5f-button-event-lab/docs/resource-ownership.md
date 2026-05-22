# 리소스 소유권

| 리소스 | 이 실험에서의 소유자 | 비고 |
|---|---|---|
| R5F core `78000000.r5f` | Phase 2 firmware 적용 중 | board manage script로 복구 가능 |
| RPMsg `rpmsg_chrdev` endpoint `14` | Phase 2 firmware와 `r5ctl` | Phase 1과 같은 endpoint를 사용해 workflow 연속성 유지 |
| DDR `r5f-status-shm@a5800000` | R5F write / A53 read | Phase 4 reserved-memory SHM, DTB 선반영 필수 |
| `MCU_GPIO0_6` | R5F input interrupt | 반드시 input-only 유지 |
| SK-AM64B SW1 | 물리 버튼 입력 | board debounce network를 거치는 active-low 신호 |

## SHM ownership 주의

`r5f-status-shm@a5800000`는 SK-AM64B booted DTB에서 reserved-memory로 먼저 확보되어야 한다.
이 전제가 없으면 R5F가 동일 물리 주소에 write할 때 Linux 일반 RAM과 충돌할 수 있다.

A53은 이 영역을 `r5ctl shm-status`에서 `/dev/mem` read-only로 확인한다.
따라서 이 경로는 root/operator 진단용으로만 취급하고, 일반 사용자 경로로 노출하지 않는다.

Phase 4 전체 요약과 실보드 검증 결과는 `docs/phase4-shm-vtm-summary.md`,
`docs/bringup-logs/2026-05-22_SK-AM64B_phase4_shm_vtm_live_validation.md`를 본다.

## GPIO Interrupt 소유권 리스크

SW1은 debounce 회로를 거친 하나의 net으로 연결되어 있으며, SoC/main-domain과 MCU-domain GPIO 경로 양쪽에 모두 도달한다. 이 실험은 그중 R5F에서 MCU-domain의 `MCU_GPIO0_6` 경로를 사용한다. 따라서 live-board 완료 판정 전에 실제 부팅된 이미지 기준으로 Linux device tree, pinctrl 상태, gpio-keys/input driver 소유 여부를 확인해야 한다.

공유된 SW1 신호를 어느 쪽에서도 output으로 구동하면 안 된다. 이 프로젝트는 `MCU_GPIO0_6`을 both-edge interrupt가 걸린 input으로 설정한다. SysConfig는 이 신호선에 대해 `MCU_SPI1_CS1` pad를 GPIO mode로 할당한다.
