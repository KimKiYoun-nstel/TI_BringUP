# Custom Board Bring-up Template

자체 보드 제작 시 복사해서 사용할 템플릿입니다.

## 보드 개요

- Board Name:
- SoC:
- DDR:
- Boot Media:
- PMIC/Power Tree:
- Debug UART:
- JTAG:

## 레퍼런스 보드 대비 차이점

| 항목 | Reference Board | Custom Board | 영향 |
|---|---|---|---|
| DDR |  |  | SPL/DDR config |
| Boot media |  |  | Boot ROM/SPL/U-Boot |
| UART |  |  | Pinmux/console |
| Ethernet |  |  | PHY/reset/clock/device tree |
| PMIC |  |  | Power sequence |
| eMMC/SD |  |  | Storage driver/device tree |

## Bring-up 순서

1. 전원 레일 확인
2. Boot mode 확인
3. UART console 확보
4. Boot ROM/SPL 진입 확인
5. DDR init 확인
6. U-Boot prompt 확보
7. Kernel boot 확인
8. RootFS mount 확인
9. Peripheral별 driver probe 확인

## 실패 로그

- 날짜:
- 증상:
- 마지막으로 보인 로그:
- 의심 지점:
- 다음 확인:
