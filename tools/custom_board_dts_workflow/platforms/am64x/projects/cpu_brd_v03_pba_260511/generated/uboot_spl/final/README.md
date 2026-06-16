# U-Boot/SPL Final Candidate

이 디렉터리는 `cpu_brd_v03_pba_260511` board project의 U-Boot/SPL 최종 후보 산출물을 둔다.

원칙:

- early pinmux와 boot media facts는 Stage-1 산출물을 따른다.
- `final/`도 `generated/`에 속하는 공식 산출물 층이다.
- DDR, binman, bootph packaging처럼 board 정책이 필요한 영역은 notes 문서에 TODO로 남긴다.
