# SBL OSPI Linux SK-AM64B Layout Note

## 목적

이 문서는 SK-AM64B 기준 R5F early boot rehearsal에서 사용할
OSPI image 역할과 검토 포인트를 정리하는 layout note 이다.

이 문서는 flash script가 아니라 설계 메모이며,
현재 단계에서는 dry-run 준비까지만 다룬다.

## 기준

- local MCU+ SDK example: `sbl_ospi_linux/am64x-evm/r5fss0-0_nortos`
- board target: SK-AM64B
- 목표: `R5F early boot -> A53 Linux boot -> attach/RPMsg 검증`

## 현재 검토 중인 image 역할

| 역할 | 예시 입력 | 기본 offset 후보 | 상태 |
|---|---|---|---|
| SBL OSPI Linux image | `sbl_ospi_linux...tiimage` | `0x0` | local example 기준 확인 |
| R5F multicore appimage | early-boot heartbeat / RPMsg appimage | `0x80000` | local example 기준 확인 |
| Linux appimage | `linuxAppimageGen` 산출물 | `0x800000` | local example 기준 확인 |
| `u-boot.img` | local Linux/U-Boot artifact 일부 | `0x300000` | local example cfg 참고 |

## 해석 주의

- `0x300000`은 현재 local cfg에서 `u-boot.img` offset으로 보인다.
- Linux appimage offset은 현재 local cfg 기준으로 `0x800000`이다.
- 따라서 후속 script나 문서는 local cfg를 source of truth로 사용해야 한다.
- partition 이름(`mtd0`, `mtd2`, `mtd5`)을 offset semantics의 대체물로 해석하면 안 된다.

## dry-run에서 반드시 보여야 할 항목

- 입력 artifact path
- target flash offset
- file size
- sha256sum
- source workspace / build provenance pointer
- board recovery reminder

## 현재 단계에서 금지하는 것

- 실제 OSPI write 자동 실행
- recovery path 미확인 상태의 `--execute`
- 보드 상호작용 없이 final offset 확정 주장
- absolute flash offset model을 partition-relative write model로 임의 치환
