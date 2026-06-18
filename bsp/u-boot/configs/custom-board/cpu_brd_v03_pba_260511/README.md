# CPU_BRD_V03_PBA_260511 U-Boot Config Notes

이 디렉터리는 `cpu_brd_v03_pba_260511` 보드의 U-Boot DTS set를 workspace build chain에 연결할 때 필요한 config override 기준을 둔다.

현재 `bringup-default` DTS set 기준 추천 override:

- A53
  - `CONFIG_DEFAULT_DEVICE_TREE="ti/k3-am6412-cpu-brd-v03-pba"`
  - `CONFIG_OF_LIST="ti/k3-am6412-cpu-brd-v03-pba"`
  - `CONFIG_SYS_MMCSD_RAW_MODE_U_BOOT_SECTOR=0x1400`
- R5 SPL
  - `CONFIG_DEFAULT_DEVICE_TREE="k3-am6412-cpu-brd-v03-pba-r5"`
  - `CONFIG_SPL_OF_LIST="k3-am6412-cpu-brd-v03-pba-r5"`
  - `CONFIG_SYS_MMCSD_RAW_MODE_U_BOOT_SECTOR=0x400`

현재 eMMC runtime fact 기준:

- Linux 확인값: `mmcblk0boot0 = 4 MiB`, `mmcblk0boot1 = 4 MiB`
- user area capacity: 약 `3.64 GiB`
- eMMC device name: `M04A11`

현재 `bringup-default`의 eMMC raw layout 가정:

- `tiboot3.bin` -> boot partition sector `0x0`
- `tispl.bin` -> boot partition sector `0x400`
- `u-boot.img` -> boot partition sector `0x1400`

이 값은 같은 U-Boot tree의 `include/configs/verdin-am62.h` precedent와 현재 custom build artifact 크기 계산을 기준으로 잡은 small-layout candidate다.

주의:

- 이 override는 DTS source projection 기준이다.
- AM64x EVM target의 `binman` packaging template는 EVM/SK DT 이름을 명시적으로 나열하므로, 최종 image packaging 전에는 `k3-am64x-binman.dtsi` 쪽 review가 필요하다.
- active eMMC boot partition(`boot0`/`boot1`)과 `partconf`는 runtime에서 다시 확인하는 것이 가장 확실하다.
