# 리소스 소유권

| 리소스 | 이 lab에서의 소유자 | 비고 |
|---|---|---|
| R5F core `78000000.r5f` | Phase 2 firmware while applied | Restored by board manage script |
| RPMsg `rpmsg_chrdev` endpoint `14` | Phase 2 firmware and `r5ctl` | Same endpoint as Phase 1 for workflow continuity |
| `MCU_GPIO0_6` | R5F input interrupt | Must remain input-only |
| SK-AM64B SW1 | Physical user input | Active-low through board debounce network |

## GPIO Interrupt 소유권 리스크

SW1은 debounce 회로를 거친 하나의 net으로 연결되어 있으며, SoC/main-domain과 MCU-domain GPIO 경로 양쪽에 모두 도달한다. 이 lab은 그중 R5F에서 MCU-domain의 `MCU_GPIO0_6` 경로를 사용한다. 따라서 live-board 완료 판정 전에 실제 부팅된 이미지 기준으로 Linux device tree, pinctrl 상태, gpio-keys/input driver 소유 여부를 확인해야 한다.

공유된 SW1 신호를 어느 쪽에서도 output으로 구동하면 안 된다. 이 프로젝트는 `MCU_GPIO0_6`을 both-edge interrupt가 걸린 input으로 설정한다. SysConfig는 이 신호선에 대해 `MCU_SPI1_CS1` pad를 GPIO mode로 할당한다.
