# R5F Early Boot Provenance

이 디렉터리는 R5F early boot rehearsal에서 생성되는
build / image generation / flash dry-run 결과의 provenance를 기록한다.

각 문서는 최소한 다음을 포함해야 한다.

- Main Repo HEAD
- MCU+ SDK workspace path와 dirty 여부
- Linux / U-Boot workspace path와 dirty 여부
- 사용한 env file
- build command
- image generation command
- artifact path
- artifact sha256
- flash target offset
- dry-run 여부 또는 실제 실행 여부
- 관련 UART/runtime log 경로

중요:

- provenance는 결과 artifact 자체보다 먼저 남겨야 한다.
- OSPI/SD/rootfs에 올라간 결과를 source of truth로 취급하지 않는다.
- recovery path를 준비하지 않은 실제 flash 실행은 provenance 상에서도 금지 대상으로 기록한다.
