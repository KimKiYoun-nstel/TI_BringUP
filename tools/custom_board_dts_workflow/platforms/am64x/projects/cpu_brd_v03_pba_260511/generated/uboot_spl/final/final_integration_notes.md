# U-Boot/SPL Final Candidate Notes

## 포함된 것

- `main_uart0` early console
- `sdhci0` eMMC boot candidate
- `ospi0` boot candidate
- `main_timer0` tick-timer 설정

## 아직 남은 것

1. eMMC 우선 부팅인지 OSPI 우선 부팅인지 최종 선택
2. LPDDR4 timing/training include chain
3. binman / packaging include
4. bootph 세부 조정

현재 final candidate는 board bring-up 시작점이며, production packaging까지 확정한 상태는 아니다.
