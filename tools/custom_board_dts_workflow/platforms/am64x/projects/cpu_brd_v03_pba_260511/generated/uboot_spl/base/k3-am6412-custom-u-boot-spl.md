# U-Boot/SPL Base Summary

- early pinmux facts: `k3-am6412-custom-early-pinmux.facts.dtsi`
- boot media candidates: `../candidates/k3-am6412-custom-boot-media.candidates.md`
- ddr candidate note: `../candidates/k3-am6412-custom-ddr.candidates.md`
- base dtsi: `k3-am6412-custom-u-boot-spl.dtsi`
- default console candidate: `UART0`

## Boot Media Candidates

- MMC0: node=sdhci0, ready=True, use_pinctrl=False, rule=CLK/CMD/DAT0 required
- OSPI0: node=ospi0, ready=True, use_pinctrl=True, rule=CLK/CSN0/D0 required
