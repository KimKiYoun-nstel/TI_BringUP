# BSP Terms

## BSP

Board Support Package. 특정 보드에서 OS가 부팅되고 주변장치가 동작하도록 필요한 bootloader, kernel, device tree, driver, rootfs 설정 묶음입니다.

## Board Bring-up

새 보드에서 전원 인가 후 부팅 로그를 확보하고, bootloader/kernel/rootfs/peripheral을 단계적으로 살리는 작업입니다.

## Device Tree

Linux Kernel에게 보드의 하드웨어 구성을 설명하는 데이터 구조입니다. CPU가 자동으로 알 수 없는 peripheral address, interrupt, pinmux, clock, regulator 연결 등을 기술합니다.

## Pinmux

SoC의 물리 핀을 어떤 기능으로 사용할지 선택하는 설정입니다. 예를 들어 같은 핀이 UART, SPI, GPIO 중 하나로 동작할 수 있습니다.

## SPL

Secondary Program Loader. 제한된 초기 환경에서 DRAM 등 필수 하드웨어를 초기화하고 다음 bootloader stage를 로드합니다.
