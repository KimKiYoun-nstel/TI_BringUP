# 2026-07-08 Pair A Official Reproduction Result

> 후속 판정: 이 문서는 당시 `SK eth0 -> TMDS eth1` sender 결과의 원본 기록이다.
> 이후 TMDS sender의 actual Qbu와 SK sender의 100 Mbps actual Qbu가 확인됐다.
> 따라서 이 문서의 counter 0을 AM64x Qbu 전체 failure나 SK hardware limitation으로
> 해석하지 않는다. 현재 canonical 결론은 [VALIDATION_STATUS.md](../VALIDATION_STATUS.md)를 따른다.

## 목적

`am64x_qbu_official_example_validation_guide.md`의 절차를 최대한 따라,
`Pair A = SK eth0 <-> TMDS eth1`에서 TI 공식 스타일 Qbu/IET 재현을 수행했다.

이번 결과의 목적은 다음 질문에 답하는 것이다.

```text
TI 공식 예제 조건에서도 actual Qbu fragment/reassembly counter가 0인가?
```

## 시험 구성

- pair: `SK eth0 <-> TMDS eth1`
- mode: plain interface, no VLAN, no netns
- sender: SK `eth0`
- receiver: TMDS `eth1`
- control
  - SK: UART
  - TMDS: `eth0` DHCP control + UART

## 공식 가이드 대비 실제 적용값

### 일치한 항목

- plain `eth0` / `eth1` 사용
- `p0-rx-ptype-rrobin off`
- `mqprio num_tc 4`
- `mode dcb`
- `fp P P P E`
- `priority 2 -> preemptible`
- `priority 3 -> express`
- sender traffic
  - preemptible: UDP `5002`, `200M`, `len 1472`
  - express: UDP `5003`, `50M`, `len 1472`
- static IP
  - SK `192.168.100.20/24`
  - TMDS `192.168.100.30/24`

### 차이점 / 편차

#### 1. 초기 시도에서 `ethtool -L ethX tx 4` 실패

첫 official-style 시도에서는 양 보드 모두 다음 명령이 실패했다.

```text
ethtool -L ethX tx 4
-> netlink error: Device or resource busy
```

따라서 첫 시도에서는 실제 TX queue 수가 계속 `8`이었다.

후속 확인 결과, 이는 현재 보드가 `TX=4`를 지원하지 않아서가 아니라,
**같은 CPSW 인스턴스의 다른 포트가 up 상태인 채로 시도했기 때문**이었다.

코드 근거:

- `am65_cpsw_set_channels()`는 `common->usage_count`가 0이 아니면 `-EBUSY` 반환

실보드 확인 결과:

- SK: `eth0`, `eth1` 둘 다 down한 뒤 `ethtool -L eth0 tx 4` 성공
- TMDS: `eth0`, `eth1` 둘 다 down한 뒤 `ethtool -L eth1 tx 4` 성공

즉 `TX=4`는 **현재 보드 조건에서도 달성 가능**하다.

#### 2. verify on 실패

공식 가이드는 먼저 `verify-enabled on`을 요구하지만,
실측 결과는 다음과 같았다.

- SK `eth0`
  - `Verification status: FAILED`
- TMDS `eth1`
  - `Verification status: UNKNOWN`
  - `TX active: off`

따라서 공식 가이드 fallback 절차대로
`verify-enabled off` force mode로 전환했다.

추가 확인:

- `TX=4` 조건을 맞춘 뒤 verify on을 다시 시도해도,
  - SK `eth0`: `Verification status: UNKNOWN`, `TX active: off`
  - TMDS `eth1`: `Verification status: FAILED`, `TX active: off`

즉 verify on 실패는 첫 시도의 `TX=8` 때문만으로 설명되지는 않는다.

#### 3. force mode 최종 MM 상태

양쪽 모두 force mode에서는 다음 상태가 확인되었다.

- `pMAC enabled: on`
- `TX enabled: on`
- `TX active: on`
- `TX minimum fragment size: 124`
- `Verification status: DISABLED`

## sender mqprio / filter 구성

SK `eth0`에 적용:

```text
mqprio num_tc 4
map 0 1 2 3 3 3 3 3 3 3 3 3 3 3 3 3
queues 1@0 1@1 1@2 1@3
hw 1
mode dcb
fp P P P E
```

egress filter:

- `dport 5002 -> skb priority 2`
- `dport 5003 -> skb priority 3`

## sender dataplane 확인

공식 스타일 재현 후 sender SK `eth0`에서 확인된 점:

- `tc filter` hit 증가
  - `priority 2` filter hit 증가
  - `priority 3` filter hit 증가
- `mqprio` qdisc accepted
- sender `tx_pri` counter 증가
  - `tx_pri2` 증가
  - `tx_pri3` 증가

즉 sender egress dataplane에서
official-style `priority 2/3` separation은 실제로 반영되었다.

## sender register 확인

sender SK `eth0` regdump 핵심 값:

- `tx_pri_map = 0x00003210`
- `IET ctrl = 0x00070105`
- `IET status = 0x00000002`

해석:

- queue/priority map가 official-style 4TC에 맞게 변했다.
- IET ctrl bit0 set -> TX preempt enable on
- IET ctrl bit2 set -> verify disabled mode
- IET ctrl bits23:16 = `0x07`
  - TC0~TC2 preemptible mask commit

즉 sender 쪽은 공식 스타일 조건에서도
**MAC dataplane arm + preemptible mask commit**이 실제 register에 반영되었다.

## traffic 결과

### sender traffic

- preemptible `5002`
  - `200 Mbit/s`
  - receiver loss 약 `0.069%`
- express `5003`
  - `50 Mbit/s`
  - receiver loss `0%`

즉 공식 traffic 자체는 정상적으로 재현되었다.

## 가장 중요한 counter 결과

### Sender: SK `eth0`

`ethtool --include-statistics --show-mm eth0` 및 `ethtool -S eth0` 결과:

- `MACMergeFragCountTx = 0`
- `MACMergeHoldCount = 0`
- `iet_tx_frag = 0`
- `iet_tx_hold = 0`

### Receiver: TMDS `eth1`

`ethtool --include-statistics --show-mm eth1` 및 `ethtool -S eth1` 결과:

- `MACMergeFragCountRx = 0`
- `MACMergeFrameAssOkCount = 0`
- `iet_rx_assembly_ok = 0`
- `MACMergeFrameAssErrorCount = 0`
- `MACMergeFrameSmdErrorCount = 3` (기존값 유지, 지배적 증가 없음)

## 판정

### Control plane accepted

YES

근거:

- `ethtool --set-mm` accepted
- `mqprio fp P P P E` accepted
- `tc filter` hit 증가

### Dataplane armed

YES

근거:

- `TX active: on`
- sender regdump에서 IET enable + preemptible TC mask commit 확인
- sender `tx_pri2/tx_pri3` separation 확인

### Actual Qbu execution observed

NO

근거:

- sender `MACMergeFragCountTx = 0`
- receiver `MACMergeFragCountRx = 0`
- receiver `MACMergeFrameAssOkCount = 0`
- sender/receiver `iet_* fragment/assembly` counter 증가 없음

## TX=4 force mode 재시험

위 편차를 줄이기 위해,
현재 보드 조건에서 official-style 절차에 가장 가깝게 다음 재시험을 수행했다.

- same CPSW instance 포트 모두 down
- `ethtool -L ethX tx 4` 성공
- `verify-enabled off` force mode
- `tx-min-frag-size 124`
- plain `eth0/eth1`
- `mqprio num_tc 4 ... mode dcb ... fp P P P E`
- official traffic 그대로

### 재시험 전 확인

- SK `eth0`
  - `TX count = 4`
  - `TX active: on`
- TMDS `eth1`
  - `TX count = 4`
  - `TX active: on`

즉 이 재시험은
**현재 보드가 official 예제의 핵심 dataplane 전제조건을 만족한 상태**에서 수행되었다.

### 재시험 결과

sender SK `eth0`:

- `tx_pri2` 증가
- `tx_pri3` 증가
- `MACMergeFragCountTx = 0`
- `iet_tx_frag = 0`
- `iet_tx_hold = 0`

receiver TMDS `eth1`:

- `MACMergeFragCountRx = 0`
- `MACMergeFrameAssOkCount = 0`
- `iet_rx_assembly_ok = 0`
- `iet_rx_frag = 0`

즉 `TX=4 force mode`까지 맞춘 뒤에도
actual fragment/reassembly 증거는 여전히 없었다.

## 결론

이번 결과는 매우 중요하다.

왜냐하면 기존 custom trial에서 남아 있던 다음 반론이 약해졌기 때문이다.

```text
"custom VLAN/netns/8TC 조건이 이상해서 counter가 0인 것 아닌가"
```

이번 official-style reproduction은

- plain interface
- no VLAN
- no netns
- official `fp P P P E`
- official `priority 2/3`
- official traffic rate

그리고 후속 재시험에서는

- `TX=4`까지 실제로 맞추고
- same-instance-port down 조건도 만족한 뒤
- force mode로 다시 수행했음에도

counter는 여전히 `0`이었다.

로 다시 수행했음에도,
fragment/reassembly counter는 여전히 전부 0이었다.

따라서 현재 시점의 가장 강한 결론은 다음이다.

```text
AM64x CPSW3G current SDK/kernel path에서는
official-style 조건과 TX=4 전제까지 맞춘 뒤에도
actual Qbu execution 증거를 확보하지 못했다.
```

즉 지금은 custom 실험 오류보다,
**CPSW3G dataplane limitation 또는 추가 undocumented 조건** 쪽 가능성이 더 강하다.

다만 verify on이 여전히 실패하므로,
strict한 의미에서는 다음 두 가지가 동시에 남아 있다.

1. current board/pair 조건에서 MAC Verify 자체가 성립하지 않는다.
2. force mode로는 MAC arm과 priority separation은 되지만 fragment/reassembly는 여전히 안 보인다.

즉 현재 보드가 official 예제의 **완전한 verify-on 조건**을 만족한다고는 아직 못 말하지만,
적어도 **TX=4 + force mode + official mqprio/traffic 조건**까지 맞춘 상태에서도 actual Qbu 증거가 안 나오는 것은 확인되었다.

## 다음 액션

1. 이 결과를 TI E2E 문의용 근거로 사용
2. 필요 시 공식 가이드 17절 순서대로
   - direction swap
   - Pair B(ICSSG) 비교
   를 수행
3. 하지만 현재 시점에서 이미
   - custom trial
   - official-style reproduction
   둘 다 counter 0이라는 근거가 확보되었음

## 추가 원인 분석: `tx 4`와 `verify on`

### 1. `ethtool -L ethX tx 4`의 실제 원인

처음에는 현재 보드가 공식 예제의 `TX=4` 조건을 만족하지 못하는 것으로 보였다.
하지만 코드와 실보드 확인 결과, 원인은 보드 한계가 아니라 **드라이버 동작 조건**이었다.

코드:

- `am65_cpsw_set_channels()`
  - `common->usage_count`가 0이 아니면 `-EBUSY`

의미:

- 같은 CPSW 인스턴스의 포트 중 하나라도 up이면 채널 수 변경이 금지된다.

실보드 결과:

- SK: `eth0`, `eth1` 둘 다 down 후 `ethtool -L eth0 tx 4` 성공
- TMDS: `eth0`, `eth1` 둘 다 down 후 `ethtool -L eth1 tx 4` 성공

즉,

```text
TX=4는 현재 보드에서도 가능하다.
초기 실패는 current board limitation이 아니라 setup ordering 문제였다.
```

### 2. `verify on`의 현재 상태

초기 sequential 시도에서는

- SK: `FAILED`
- TMDS: `UNKNOWN`

이 나와 타이밍 문제 가능성이 있었다.

그래서 양쪽을

- same-instance 포트 down
- `TX=4`
- `verify-enabled on`
- `tx-min-frag-size 124`

상태로 미리 준비한 뒤,
`ip link set up`을 거의 동시에 실행했다.

### 3. 동시 bring-up 결과

#### SK `eth0`

- link: up
- `Verification status: FAILED`
- `TX active: off`
- register
  - `IET ctrl = 0x00070101`
  - `IET status = 0x00000002`

해석:

- `0x00000002`는 `AM65_CPSW_PN_MAC_VERIFY_FAIL`
- 즉 SK는 verify state machine을 실제로 돌렸고,
  결과는 **timeout/무응답이 아니라 peer verify failure 판정**에 가깝다.

#### TMDS `eth1`

- link: up
- `Verification status: SUCCEEDED`
- `TX active: on`
- register
  - `IET ctrl = 0x00000101`
  - `IET status = 0x00000001`

해석:

- `0x00000001`은 `AM65_CPSW_PN_MAC_VERIFIED`
- TMDS는 같은 direct pair에서 verify를 성공했다.

### 4. verify 원인에 대한 현재 결론

이 결과는 매우 중요하다.

왜냐하면 다음 사실이 분리되었기 때문이다.

```text
verify on은 현재 pair 전체에서 불가능한 것이 아니다.
현재는 SK 쪽만 실패하는 비대칭 문제다.
```

즉 현재 가장 가능성이 큰 설명은 다음이다.

1. SK `eth0` 측 verify state machine이 peer response를 실패로 판정한다.
2. TMDS `eth1`는 같은 링크에서 verify를 성공한다.
3. 따라서 이 문제는 단순 cable/link-down 문제보다는,
   SK side-specific behavior 또는 pair asymmetry issue 가능성이 크다.

### 5. stale preemptible mask 가설 배제

한 가지 의심점은 SK sender 쪽 IET ctrl register에 이전 custom trial의
preemptible mask(`0x07`)가 남아 있는 것이 verify 실패를 유발하는지 여부였다.

이를 확인하기 위해 진단용으로 SK `eth0`의 IET ctrl register를
`0x00000109`로 직접 써서 preemptible mask를 0으로 만든 뒤,
TMDS와 다시 동시 `verify on` bring-up을 수행했다.

결과:

- SK `eth0`
  - `IET ctrl = 0x00000101`
  - `IET status = 0x00000002`
  - `Verification status: FAILED`
- TMDS `eth1`
  - `IET ctrl = 0x00000101`
  - `IET status = 0x00000001`
  - `Verification status: SUCCEEDED`

즉 stale preemptible mask는 verify 실패의 직접 원인이 아니었다.

정리하면,

```text
SK verify failure는 stale mqprio mask artifact가 아니라,
현재 Pair A에서 SK side-specific verify failure로 보는 것이 더 타당하다.
```

### 6. dataplane 해석에 주는 영향

이 결과는 `force mode` 해석에도 영향을 준다.

- `verify on`은 pair 전체가 안 되는 게 아님
- 하지만 current direct pair에서 **SK sender가 verify를 성공하지 못함**

따라서 다음 두 문장을 동시에 유지해야 한다.

```text
1. official verify-on path는 현재 Pair A에서 완전히 성립하지 않는다.
2. 그러나 force mode + TX=4 + official mqprio/traffic까지 맞춘 상태에서도 actual fragment/reassembly counter는 0이다.
```

즉 verify failure 하나만으로 actual counter 0을 전부 설명할 수는 없다.

### 7. 현재 남은 가장 강한 의심점

1. SK `eth0`의 verify failure root cause
   - SK side-specific behavior
   - PHY/link timing asymmetry
   - undocumented board-specific constraint

2. force mode에서조차 fragment/reassembly가 안 보이는 이유
   - CPSW3G dataplane limitation
   - additional undocumented trigger requirement
