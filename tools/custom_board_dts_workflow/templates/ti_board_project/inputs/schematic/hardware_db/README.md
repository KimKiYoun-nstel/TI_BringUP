# Schematic Hardware DB

이 디렉터리에는 PDF 회로도에서 미리 정리한 schematic-derived backdata를 둔다.

의도:

- PDF 원문을 매번 다시 읽지 않기 위한 재사용 입력
- boot media, power tree, interface role, reset/interrupt, unresolved 정책 후보를 구조화

권장 파일 예:

- `00_board_identity.yaml`
- `01_memory_boot_media.yaml`
- `02_power_tree.yaml`
- `03_interfaces.yaml`
- `04_reset_interrupt_gpio.yaml`
- `05_dts_generation_policy.yaml`
- `06_unresolved_items.yaml`

주의:

- `.NET`을 대체하지 않는다.
- `.NET`은 전기적 연결 원천이고, 이 DB는 회로도 의미 backdata다.
