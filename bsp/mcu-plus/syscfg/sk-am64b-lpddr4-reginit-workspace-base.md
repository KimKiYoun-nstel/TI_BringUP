# SK-AM64B LPDDR4 Reginit Workspace Base

## 목적

이 문서는 SK-AM64B `SBL OSPI Linux` bring-up에서 실제 원인 수정으로 확인된
LPDDR4 `board_ddrReginit.h` workspace base를 고정한다.

이 파일은 repo-managed standalone asset와 현재 workspace base의
**정확한 경로, 해시, 의미**를 함께 고정하는 pinned note이다.

## repo-managed standalone asset

- 경로: `bsp/mcu-plus/syscfg/board_ddrReginit_sk_am64b_lpddr4.h`
- sha256: `791481fcab5c1761df4eca015b908dc09d378a7347b368cf9eaebcddaf74c9e5`

의미:

- 현재 검증된 LPDDR4 `board_ddrReginit.h`를 repo 안에 standalone asset로 보관한다.
- workspace file과 같은 내용이므로, clean workspace 재구성 시 source asset로 사용할 수 있다.

## 현재 workspace base

- 경로: `workspace/mcu_plus_sdk_am64x_12_00_00_27/source/drivers/ddr/v0/soc/am64x_am243x/board_ddrReginit.h`
- line count: `4390`
- sha256: `791481fcab5c1761df4eca015b908dc09d378a7347b368cf9eaebcddaf74c9e5`

header 확인값:

```c
#define DDR_TYPE LPDDR4
```

파일 head marker:

```text
/* Auto-generated from U-Boot k3-am64-sk-lp4-1600MTs.dtsi */
```

## 의미

확정된 사실:

- external MCU+ SDK original의 공용 `board_ddrReginit.h`는 SK-AM64B 실보드 LPDDR4와 맞지 않았다.
- 위 workspace base file은 U-Boot SK LPDDR4 dtsi 기반으로 변환된 현재 검증 자산이다.
- `SBL -> BL31/BL32/BL33 DDR 적재 -> U-Boot -> Linux` 성공은 이 workspace base를 전제로 한다.

## 현재 repo 관리 원칙

1. early-boot 원인 정리의 본질 수정은 이 LPDDR4 reginit delta다.
2. SBL `main.c`의 다수 debug marker는 검증 보조 수단이고, root cause fix 자체는 아니다.
3. 현재는 standalone asset + workspace base hash를 함께 고정해 둔다.
4. replay 가치가 큰 `sbl_ospi_linux` source delta는 별도 patch로 관리한다.
