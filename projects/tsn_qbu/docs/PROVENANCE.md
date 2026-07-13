# Qbu Validation Provenance

## 목적

이 문서는 Qbu validation certificate가 어떤 kernel, DTB, rootfs baseline에서 얻어졌는지
고정한다. hash가 다르면 기존 certificate를 그대로 재사용하지 않고 재검증해야 한다.

## Verified Runtime Image

2026-07-13 validation 당시 두 보드는 같은 kernel image hash로 실행됐다.

| 항목 | 값 |
|---|---|
| kernel release | `6.18.13-ti-00778-gc21449208550-dirty` |
| Linux source base commit | `c214492085504176b9c252a7175e4e60b4b442af` |
| image path | `/boot/Image-6.18.13-ti-00778-gc21449208550-dirty` |
| Image SHA-256 | `bfd8a438f933f02fed44fd66baf7f839385a9814bc6bc3df693b44b752818361` |
| SK DTB | `/boot/dtb/ti/k3-am642-sk.dtb` |
| SK DTB SHA-256 | `6da17128d08081c731a2ed952027b53adf32d72d7e7d95ec6dca24a5813052df` |
| TMDS DTB | `/boot/dtb/ti/k3-am642-evm.dtb` |
| TMDS DTB SHA-256 | `b3eba6883bf47bbb91e2725a98b6bf42c3b91c6bd93f1e0bc627734842f65cbc` |
| rootfs device | both `/dev/mmcblk1p2` |

## Historical Artifact Limitation

위 Image는 `-dirty` build이며, 이 repo에는 image를 만든 workspace diff/patch와 build
provenance가 없다. 현재 `workspace/ti-linux-kernel-sdk12`은 clean `c21449208` 상태다.
현재 workspace `.config`도 `CONFIG_NET_PKTGEN`을 enable하지 않는다.

따라서 다음 문장은 아직 성립하지 않는다.

```text
clean source checkout + managed patch set으로 validation kernel을 rebuild할 수 있다.
```

hash는 historical 실행 artifact 식별용이며 source reproducibility를 대체하지 않는다.
그러나 Qbu feature에 managed image delta가 없으므로, 이 artifact limitation은 Qbu 설정 절차의
blocker가 아니다. exact prebuilt image certificate가 필요할 때만 해당 image에서 재검증한다.

## Qbu Change Audit

현재 repo에서 확인되는 Qbu-specific 변경은 rootfs network policy뿐이다. Qbu kernel source,
DTS/DTB, U-Boot patch는 관리되지 않았고 그 변경을 적용했다는 deployment record도 없다.

그러나 historical validation Image의 source diff가 없으므로, dirty Image에 Qbu와 무관한
변경만 있었다고 증명할 수도 없다. 이 불확실성 때문에 historical certificate와 clean managed
base를 분리한다. 기준은 [CLEAN_BASE_CONTRACT.md](CLEAN_BASE_CONTRACT.md)를 따른다.

## Rootfs Baseline Asset

clean baseline의 persistent 변경은 다음 overlay script로 관리한다.

- SK: `rootfs/overlays/sk-am64b-qbu-clean-baseline/usr/local/sbin/qbu-clean-baseline-sk.sh`
- TMDS: `rootfs/overlays/tmds64evm-qbu-clean-baseline/usr/local/sbin/qbu-clean-baseline-tmds.sh`

이 script는 이전 TSN DSCP/PCP network profile을 `.qbu-disabled`로 이동하고 data port를
L2-only로 만든다. 적용 후 reboot 또는 `systemd-networkd` restart가 필요하다.
