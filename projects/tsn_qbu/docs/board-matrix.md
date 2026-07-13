# AM64x Qbu Board Matrix

## 현재 보드 매핑

### SK-AM64B

- control: UART
- `eth0`: `am65-cpsw-nuss`, CPSW `port@1`
- `eth1`: `am65-cpsw-nuss`, CPSW `port@2`

### TMDS64EVM

- control: `eth0` (runtime DHCP 또는 UART)
- `eth0`: `am65-cpsw-nuss`, CPSW `port@1`
- `eth1`: `am65-cpsw-nuss`, CPSW `port@2`
- `eth2`: `icssg-prueth`, ICSSG1 `port@0`

## 확인된 직결 페어

```text
Canonical: TMDS eth1 <----> SK eth1
Comparative: TMDS eth2 <----> SK eth0
TMDS eth0 = control port
SK control = UART
```

## Qbu 관점의 역할 후보

### Canonical CPSW Pair

- 송신 후보 1: SK `eth1` -> TMDS `eth1`
- 송신 후보 2: TMDS `eth1` -> SK `eth1`
- 성격: CPSW <-> CPSW
- 장점: 같은 MAC family라 baseline Qbu bring-up에 유리

### Comparative CPSW/ICSSG Pair

- 송신 후보 1: SK `eth0` -> TMDS `eth2`
- 송신 후보 2: TMDS `eth2` -> SK `eth0`
- 성격: CPSW <-> ICSSG
- 장점: AM64x의 서로 다른 TSN-capable MAC 조합 비교 가능
- 주의: 첫 실험 기준으로는 driver variance가 더 큼
