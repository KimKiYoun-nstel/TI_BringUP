# U-Boot/SPL DTS Handoff Notes

## 왜 이 세트로 정리했는가

이 세트는 bootloader source tree에 그대로 merge하거나 편집할 수 있는 최소 DTSI 세트를 전달하기 위한 것이다.

남긴 것은 다음뿐이다.

1. U-Boot/SPL 본문 fragment
2. early pinctrl fragment
3. 사람이 읽는 선택 이유/남은 정책 메모

## 이번 선택에 포함한 것

1. `main_uart0` early console
2. `sdhci0` eMMC boot candidate
3. `sdhci1` disable
4. `ospi0` boot candidate
5. `main_timer0` tick-timer

## 아직 보류한 것

1. eMMC 우선 부팅인지 OSPI 우선 부팅인지 최종 선택
2. LPDDR4 timing/training include chain
3. binman / packaging include
4. bootph 세부 조정

즉 현재 세트는 bring-up 시작점으로는 충분하지만, production packaging이 확정된 세트는 아니다.
