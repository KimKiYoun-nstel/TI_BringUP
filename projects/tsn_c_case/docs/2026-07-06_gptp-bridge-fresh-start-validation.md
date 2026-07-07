# 2026-07-06 gPTP Bridge Fresh-Start Validation

## 목적

- `gptp_icssg_switch` 이식 firmware가 예제 목적대로
- `SK eth0 (GM/master 후보) -> TMDS gPTP Bridge -> SK eth1 (slave 후보)`
- 구조에서 gPTP 시간 동기화를 성립시키는지 확인한다.

## 구성

- `SK eth0 <-> TMDS ICSSG port1`
- `TMDS ICSSG port2 <-> SK eth1`
- SK는 기존 `br-tsn`에서 `eth0/eth1`을 제거하고 netns로 분리했다.
- TMDS는 U-Boot temporary override로 `gptp_icssg_linux_remoteproc_r5f0_0_test.out`를 fresh boot 했다.

## 사용한 ptp4l 설정

GM 후보(`/tmp/gm.conf`):

```text
[global]
network_transport L2
delay_mechanism P2P
time_stamping hardware
twoStepFlag 1
transportSpecific 1
ptp_dst_mac 01:80:C2:00:00:0E
priority1 16
priority2 16
summary_interval 1
logging_level 6
tx_timestamp_timeout 100
```

Slave 후보(`/tmp/slv.conf`):

```text
[global]
network_transport L2
delay_mechanism P2P
time_stamping hardware
twoStepFlag 1
transportSpecific 1
ptp_dst_mac 01:80:C2:00:00:0E
priority1 248
priority2 248
summary_interval 1
logging_level 6
tx_timestamp_timeout 100
```

## 실행 요약

- SK:
- `br-tsn` 삭제 후 `eth0 -> n0`, `eth1 -> n1`로 분리
- `ip netns exec n0 timeout 90 tcpdump -i eth0 -nne -tttt ether proto 0x88f7`
- `ip netns exec n1 timeout 90 tcpdump -i eth1 -nne -tttt ether proto 0x88f7`
- `ip netns exec n1 timeout 90 ptp4l -i eth1 -f /tmp/slv.conf -m`
- `ip netns exec n0 timeout 90 ptp4l -i eth0 -f /tmp/gm.conf -m`
- TMDS:
- U-Boot에서 `firmware-name=gptp_icssg_linux_remoteproc_r5f0_0_test.out` temporary override 적용
- Linux boot 후 `78000000.r5f`가 `remoteproc0`으로 올라왔고 test firmware running 확인

## 관찰 결과

### TMDS fresh start

- `remoteproc0 78000000.r5f`
- `state=running`
- `fw=gptp_icssg_linux_remoteproc_r5f0_0_test.out`

### SK eth0 ptp4l

```text
ptp4l[7010.561]: selected /dev/ptp0 as PTP clock
ptp4l[7010.576]: port 1 (eth0): INITIALIZING to LISTENING on INIT_COMPLETE
ptp4l[7017.711]: port 1 (eth0): LISTENING to MASTER on ANNOUNCE_RECEIPT_TIMEOUT_EXPIRES
ptp4l[7017.712]: selected local clock 28b5e8.fffe.cc2a3f as best master
ptp4l[7017.712]: port 1 (eth0): assuming the grand master role
```

판정:

- `eth0`는 기대대로 GM/master 역할로 self-elect 됨

### SK eth1 ptp4l

```text
ptp4l[7005.527]: selected /dev/ptp0 as PTP clock
ptp4l[7005.540]: port 1 (eth1): INITIALIZING to LISTENING on INIT_COMPLETE
ptp4l[7012.011]: port 1 (eth1): LISTENING to MASTER on ANNOUNCE_RECEIPT_TIMEOUT_EXPIRES
ptp4l[7012.011]: selected local clock 70ff76.fffe.1ff287 as best master
ptp4l[7012.011]: port 1 (eth1): assuming the grand master role
```

판정:

- `eth1`는 `UNCALIBRATED -> SLAVE`로 가지 못하고 self-GM이 됨

주의:

- `eth0`와 `eth1` 모두 `selected /dev/ptp0 as PTP clock`으로 같은 PHC를 사용했다.
- 따라서 두 `ptp4l` instance는 완전히 독립된 물리 clock pair는 아니다.
- 다만 이번 FAIL의 핵심 증거인 foreign `0x88f7` frame 부재는 이 caveat와 별개다.

### SK eth0 tcpdump 요약

- `/tmp/tcp_eth0.log`: 242 lines
- `0x88f7` frame은 지속적으로 보임
- 대표 frame:
  - `peer delay req`
  - `announce`
  - `sync`
  - `follow up`
- 관찰된 src MAC은 `28:b5:e8:cc:2a:3f`(SK eth0)만 확인
- `70:ff:76:1f:f2:87`(SK eth1) 또는 TMDS 쪽에서 들어온 foreign PTP frame은 확인되지 않음

### SK eth1 tcpdump 요약

- `/tmp/tcp_eth1.log`: 282 lines
- `0x88f7` frame은 지속적으로 보임
- 대표 frame:
  - `peer delay req`
  - `announce`
  - `sync`
  - `follow up`
- 관찰된 src MAC은 `70:ff:76:1f:f2:87`(SK eth1)만 확인
- `28:b5:e8:cc:2a:3f`(SK eth0) source PTP frame은 0건

### TMDS remoteproc trace

`/sys/kernel/debug/remoteproc/remoteproc0/trace0`에서 확인:

```text
[r5f0-0]   307.383034s : ERR:cbase:cb_lld_sendto:sent failed -2
[r5f0-0]   307.383042s : ERR:gptp:000307-375053:gptpnet_send:sent SIGNALING failed
[r5f0-0]   307.633035s : ERR:cbase:cb_lld_sendto:sent failed -2
[r5f0-0]   307.633043s : ERR:gptp:000307-625069:gptpnet_send:sent SIGNALING failed
[r5f0-0]   311.003033s : domain=0, offset=0nsec, hw-adjrate=0ppb
[r5f0-0]   311.003042s :         gmsync=true, last_setts64=0nsec
```

추가 관찰:

- same trace window에서 `gptpnet_send:sent SIGNALING failed` 3회 확인
- `cb_lld_sendto:sent failed -2` 3회 확인
- `log ovflow!` 93회 확인
- 이번 회수본에서는 `tilld0/tilld1 open`, port별 `asCapable`, `PDelay/Sync/Announce RX/TX`를 직접 보여주는 초기 trace는 확보하지 못했다.

## PASS / FAIL 판정

### PASS

- SK eth0: MASTER/GM self-election 확인
- TMDS: fresh start 성공
- TMDS: test firmware running 확인
- TMDS trace: `gmsync=true`, `offset=0nsec` 상태 문자열 확인

### FAIL

- SK eth1: `0x88f7` foreign frame 수신 실패
- SK eth1: `UNCALIBRATED -> SLAVE` 전이 실패
- SK eth1: offset convergence 검증 불가
- end-to-end 목표인
- `SK eth0 (GM) -> TMDS gPTP Bridge -> SK eth1 (SL)`
- 구조의 gPTP 시간 동기화 성립 실패

## 실패 분류

### 1. SK eth0가 GM이 되지 않는 문제

- 해당 없음
- `eth0`는 self-GM이 정상 형성됨

### 2. TMDS port1 RX 문제

- 이번 수집본만으로 확정 불가
- 직접적인 port1 RX trace는 확보하지 못함

### 3. TMDS port2 TX 문제

- 강하게 의심됨
- `eth1` 캡처에서 `eth0` source PTP frame이 0건이므로 bridge forwarding/TX 증거가 없음

### 4. SK eth1이 frame은 받지만 SLAVE가 안 되는 문제

- 해당 없음
- `eth1`는 foreign gPTP frame 자체를 받지 못한 상태로 보임

### 5. `gptpnet_send failed` 상세

- trace에 `SIGNALING failed`만 남아 있으며 portIndex는 현재 trace만으로 식별 불가
- return code는 `-2`

## 현재 결론

- 이번 fresh-start 검증 기준으로는
- `gptp_icssg_switch` 이식 firmware가 예제 목표대로
- `SK eth0 -> TMDS bridge -> SK eth1`
- 방향의 gPTP time sync를 성립시키지 못했다.
- 현재 증적상 `eth0`와 `eth1`은 서로의 gPTP frame을 보지 못하고 각자 self-GM으로 동작했다.

## 다음 확인 필요

- TMDS trace overflow를 줄이거나 boot 직후 즉시 trace를 회수해 `tilld0/tilld1`, `asCapable`, port별 RX/TX 초기 상태를 확보
- `gptpnet_send:sent SIGNALING failed`의 portIndex/messageType mapping 추가 instrumentation 확보
- `gptp_icssg_switch` 예제가 transparent bridge forwarding 모델인지, host-terminate/trap 모델인지 코드 기준으로 재확인

## 추가 검증: remoteproc DMA memory relocation retry

### 변경 내용

- remoteproc build에서 donor와 다르게 cacheable DDR `.bss`에 놓이던 아래 영역을 non-cache carveout으로 이동하도록 linker override를 추가했다.
  - `.icss_mem`
  - `.enet_dma_mem`
- 관련 파일:
  - `workspace/.../linker.remoteproc.cmd`
  - `workspace/.../Release/subdir_rules.mk`

### 빌드 확인

- 새 map에서 아래 배치 확인:
  - `.icss_mem` -> `0xA0000000`
  - `.enet_dma_mem` -> `0xA0034000`
- 즉 donor parity 의도로 넣은 ICSSG shared pool / DMA pool relocation은 실제 산출물에 반영됨

### boot health 판정

- TMDS temporary override boot는 정상적으로 `login:`까지 도달
- `remoteproc0 78000000.r5f`
- `fw=gptp_icssg_linux_remoteproc_r5f0_0_test.out`
- 이번 수정으로 보드 boot failure는 관찰되지 않음

### 재검증 결과

- SK eth0 `ptp4l`
  - 여전히 `assuming the grand master role`
- SK eth1 `ptp4l`
  - 여전히 `assuming the grand master role`
- SK tcpdump count
  - `eth1`에서 `28:b5:e8:cc:2a:3f` source frame: `0`
  - `eth1`에서 `70:ff:76:1f:f2:87` source frame: `293`
  - `eth0`에서 `70:ff:76:1f:f2:87` source frame: `0`
  - `eth0`에서 `28:b5:e8:cc:2a:3f` source frame: `289`
- TMDS trace0
  - `ERR:cbase:cb_lld_sendto:sent failed -2` 지속
  - `ERR:gptp:...:gptpnet_send:sent SIGNALING failed` 지속
  - `domain=0, offset=0nsec, hw-adjrate=0ppb`
  - `gmsync=true`
  - `log ovflow!` 지속

### 판정

- `.icss_mem` / `.enet_dma_mem` relocation만으로는 문제를 해결하지 못했다.
- 이번 가설은 다음과 같이 정리한다.
  - boot 안정성 개선/유지는 확인
  - end-to-end gPTP bridge forwarding/sync failure에는 직접적인 개선 효과 없음

## 추가 검증: TX event probe + manual poll workaround

### 변경 내용

- `EnetApp_getTxDmaHandle()`에서 PTP TX channel callback registration을 probe wrapper로 감쌌다.
- trace 항목:
  - `stage=tx_evt state=register`
  - `stage=tx_evt state=notify`
- 또한 main loop에서 `ENET_DMA_TX_CH_PTP`에 대해 `notifyCb`를 주기적으로 직접 호출하는 poll workaround를 추가했다.
  - 의도: TX done IRQ가 안 와도 `LLDEnetTxNotifyCb -> EnetDma_retrieveTxPktQ()` 경로를 강제로 돌려 free buffer reclaim이 살아나는지 확인

### 확인된 사실

- boot 직후 trace에서 registration은 확인됨:

```text
[RPROC_TRACE] stage=tx_evt state=register code=0 ch=1 txChNum=49665 hTxCh=A0193B20 cb=A01456B9
```

- 즉 PTP TX channel(`ch=1`)에 대해 callback registration 자체는 성립한다.

### workaround 결과

- 30초/90초 traffic window 모두에서 SK 관찰 결과는 이전과 동일했다.
  - `eth0` self-GM 유지
  - `eth1` self-GM 유지
  - foreign `0x88f7` 여전히 0건
- manual poll을 넣어도 end-to-end gPTP forwarding/sync에 변화가 없었다.

### 해석

- 이 결과는 원인을 한 단계 더 좁힌다.
- 만약 문제가 단순히 `TX done interrupt 미도착`만이었다면,
- main loop에서 `notifyCb`를 직접 호출했을 때
  - `EnetDma_retrieveTxPktQ()`를 통해 reclaim이 살아나고 증상이 완화될 가능성이 있었다.
- 그러나 실제로는 변화가 없었다.

현재 더 유력한 쪽:

- packet submit 이후 TX completion 자체가 정상적으로 돌아오지 않음
- 즉 단순 `event callback delivery` 문제가 아니라
- 더 아래의 TX completion / DMA completion / egress path 문제 가능성이 높다.

## 추가 검증: `tx_evt` stats retry와 throttle 재부팅

### 변경 내용

- `Release/syscfg/ti_enet_open_close.c`에 PTP TX probe 구조체를 확장해 `EnetDma_getTxChStats()` 기반 채널 통계를 읽도록 추가 계측했다.
- `tsnapp_icssg_main.c`에서는 이 통계 호출을 매 loop가 아니라 약 1초 간격으로만 호출하도록 줄였다.
- 목적:
  - `cb_lld_sendto ... -2`가 실제로 TX free/reclaim 고갈과 연결되는지 확인
  - `state=notify`가 실제로 발생하는지 trace에서 분리 확인

### boot / runtime 사실

- temporary override boot는 다시 정상적으로 `login:`까지 도달했다.
- 이번 reboot에서는 `78000000.r5f`가 `remoteproc0`로 올라왔다.
- 즉 remoteproc sysfs/debugfs 번호는 계속 변동하며, 이번 검증에서는 `remoteproc0` 기준으로 trace를 봤다.

### TMDS trace 결과

`/sys/kernel/debug/remoteproc/remoteproc0/trace0`에서 확인:

```text
[r5f0-0] ... cb_lld_sendto:sent failed -2
[r5f0-0] ... ERR:gptp:...:gptpnet_send:sent SIGNALING failed
[r5f0-0] ... [RPROC_TRACE] stage=tx_evt state=error code=-13 stats failed ch=1 txChNum=49665
```

추가 count:

```text
stage=tx_evt state=register : 0
stage=tx_evt state=notify   : 0
stage=tx_evt state=error    : 3
```

### SK 재검증 결과

- `ptp4l` 결과는 동일했다.
  - `eth0`: self-GM
  - `eth1`: self-GM
- 15초 `ether proto 0x88f7` capture count:
  - `eth1`에서 `28:b5:e8:cc:2a:3f` source frame: `0`
  - `eth1`에서 `70:ff:76:1f:f2:87` source frame: `31`
  - `eth0`에서 `70:ff:76:1f:f2:87` source frame: `0`
  - `eth0`에서 `28:b5:e8:cc:2a:3f` source frame: `33`

### 판정

- `EnetDma_getTxChStats()`는 현재 PTP TX channel 관측에 쓸 수 없었다.
  - 현재 반환값은 `-13`
- throttled retry 이후에도 trace buffer에 `state=notify`는 잡히지 않았다.
- 같은 window에서 `cb_lld_sendto:sent failed -2`와 `gptpnet_send:sent SIGNALING failed`는 계속 반복됐다.

현재까지의 추가 해석:

- app submit 이후 reclaim/completion 관측은 여전히 성립하지 않는다.
- `-2`는 계속 `LLDENET_E_NOBUF` 쪽 의미와 정합하지만,
  현재 계측만으로는
  - completion event 자체가 오지 않는지
  - 더 아래에서 packet reclaim이 안 되는지
  - directed egress path에서 drop되는지
  를 완전히 분리하지는 못했다.

## 추가 검증: `notify count` probe

### 변경 내용

- `EnetApp_txEventProbeCb()`가 올린 `callCount`를 1초마다 trace로 노출하도록 probe를 추가했다.
- 목적:
  - 실제 TX event callback delivery가 정말 살아 있는지 확정
  - manual poll과 별개로 hardware-driven notify가 오는지 분리

### TMDS trace 결과

`/sys/kernel/debug/remoteproc/remoteproc0/trace0`:

```text
[r5f0-0] ... stage=tx_evt state=count ... ch=1 txChNum=49665 notify=100
[r5f0-0] ... stage=tx_evt state=error code=-13 stats failed ch=1 txChNum=49665 notify=100
[r5f0-0] ... ERR:cbase:cb_lld_sendto:sent failed -2
[r5f0-0] ... ERR:gptp:...:gptpnet_send:sent SIGNALING failed
```

### SK 결과

- 이번 12초 window에서도 동일:
  - `eth0` self-GM
  - `eth1` self-GM

### 판정

- 실제 TX notify callback delivery는 살아 있다.
  - `notify=100` 확인
- 따라서 현재 문제를 `TX done IRQ/event 미도착`으로 보는 해석은 더 약해졌다.
- 남는 유력 후보는 다음 둘이다.
  - callback 이후 `retrieveTxPktQ()` / reclaim 쪽에서 free buffer가 회복되지 않는 문제
  - TX submit은 되더라도 lower completion/egress path에서 packet lifecycle이 비정상인 문제

현재까지의 해석 업데이트:

- `manual poll`이 효과 없었고,
- `real notify callback`도 실제로 들어온다.
- 그럼에도 `cb_lld_sendto ... -2`가 계속되므로,
  문제의 중심은 이제 **event delivery 이전이 아니라 reclaim/completion 이후 또는 더 낮은 egress lifecycle** 쪽으로 더 기운다.

## 추가 검증: source-linked `tsn_icssg_combase` override

### 변경 내용

- workspace의 `source/networking/tsn/tsn-stack/tsn_combase/tilld/sitara/lldenet.c`에 넣어 둔 계측을 실제로 쓰기 위해,
  local `tsn_icssg_combase-freertos.am64x.r5f.ti-arm-clang.release.lib`를 rebuild했다.
- 이후 project `Release/makefile`에서 외부 SDK prebuilt 대신 workspace local lib를 직접 링크하도록 바꿨다.
- 목적:
  - `LLDEnetSendMultiScatter()` / `LLDEnetRetrieveTxDonePkts()`의
    - `no-buf`
    - `submitCalls`
    - `doneCalls`
    계측을 실제 runtime에 태우기 위함

### 로컬 산출물 확인

- rebuilt lib와 최종 ELF 모두에 아래 문자열이 실제 포함됨을 확인했다.

```text
no-buf freeQ=%u need=%u submitCalls=%u ... doneCalls=%u ...
submitCalls=%u submitPkts=%u sent=%u freeQ=%u
doneCalls=%u donePkts=%u lastDone=%u freeQ=%u
```

즉 source-linked local combase override 자체는 실제 산출물에 반영되었다.

### TMDS runtime 결과

- temporary override boot는 다시 `login:`까지 정상 도달했다.
- `remoteproc0` 기준 trace 확인 결과:

```text
[RPROC_TRACE] stage=tx_evt state=register ... ch=1 txChNum=49665 ...
[RPROC_TRACE] stage=tx_evt state=count ... ch=1 txChNum=49665 notify=0
[RPROC_TRACE] stage=tx_evt state=error code=-13 stats failed ch=1 txChNum=49665 notify=0
```

- 반면 이전 build에서 반복되던 아래 문자열은 이번 source-linked combase build에서는 trace에 잡히지 않았다.

```text
cb_lld_sendto:sent failed -2
gptpnet_send:sent SIGNALING failed
```

- 또한 이번 build에서는 trace에서 다음 항목도 추가로 보이지 않았다.
  - `stage=mac_stats`
  - `domain=0, offset=...`
  - `gmsync=true`

### SK 결과

- slave 쪽 `ptp4l`은 여전히 self-GM으로 끝났다.
- broad capture 재시도:

```text
tcpdump -i eth1 -nne -tttt "vlan or ether proto 0x88f7"
0 packets captured
```

즉 source-linked combase build에서도 `eth1` foreign PTP frame은 여전히 0건이다.

### 해석

- 이 분기는 중요한 부정 실험이다.
- `-2` / `SIGNALING failed`가 사라져도 end-to-end gPTP sync는 여전히 성립하지 않았다.
- 따라서 현재 해석은 다음처럼 갱신한다.

1. `cb_lld_sendto ... -2`는 근본 원인이라기보다 2차 증상일 가능성이 커졌다.
2. 실제 핵심 문제는 여전히 더 아래의 forwarding/egress lifecycle 또는 frame generation 쪽에 남아 있을 수 있다.
3. 특히 이번 build에서 `notify=0`이 유지되고 broad capture도 0건이므로,
   현재 실험 조합에서는 PTP TX path 자체가 runtime에서 적극적으로 돌지 않거나,
   돌더라도 wire-visible frame을 만들지 못하는 상태로 해석된다.

### 주의

- source-linked local combase override는 현재 root-cause isolation용 실험 자산이다.
- prebuilt path와 runtime behavior가 달라졌으므로,
  이 분기 결과를 donor parity로 곧바로 해석하면 안 된다.
- 그러나 "`-2`를 없애도 foreign frame은 안 생긴다"는 사실 자체는 매우 유의미하다.

## 추가 검증: source-linked `tsn_icssg_gptp` send-path probe

### 변경 내용

- workspace의 `source/networking/tsn/tsn-stack/tsn_gptp/tilld/lld_gptpnet.c`에
  `gptpnet_send()` entry logging을 추가했다.
- local `tsn_icssg_gptp-freertos.am64x.r5f.ti-arm-clang.release.lib`를 rebuild하고,
  project `Release/makefile`이 이 local gptp lib를 직접 링크하도록 바꿨다.
- probe 문자열은 최종 ELF에 실제 포함됨을 확인했다.

```text
%s: ndev=%d msg=%s msgtype=%d seqid=%u domain=%u count=%u len=%u
```

### TMDS trace 결과

SK 쪽 traffic window 이후 `remoteproc0/trace0`에서 확인:

```text
grep 'gptpnet_send:' ...  -> 0 hits
grep 'stage=tx_evt state=count' ...
  notify=0
  notify=0
```

즉 이 source-linked combase+gptp build에서는:

- `gptpnet_send()` entry log 자체가 한 번도 보이지 않음
- PTP TX notify count도 계속 `0`

### SK 결과

- `eth1`는 여전히 self-GM
- slave lock 없음

### 판정

- 이 분기에서는 단순히 `cb_lld_sendto ... -2`가 사라진 정도가 아니라,
  **gPTP send path 자체가 trace 기준으로 진입하지 않는 상태**가 됐다.
- 따라서 이 source-linked override 분기는 prebuilt baseline과 runtime 성질이 더 달라졌고,
  root-cause isolation reference로는 쓰되 donor parity 해석 기준으로 삼기에는 부적합하다.

현재까지의 보수적 결론:

1. prebuilt baseline path에서는
   - real TX notify는 온다
   - `cb_lld_sendto ... -2` / `SIGNALING failed`가 반복된다
2. source-linked override path에서는
   - `-2`는 사라지지만
   - `gptpnet_send()` entry도 안 보이고
   - broad foreign PTP capture도 여전히 0건이다

즉 현재 investigation의 기준선은 계속 **prebuilt baseline path**로 유지하는 것이 맞다.

## 추가 검증: local gptp + prebuilt combase로 `site_sync -> port2` 경로 재분해

### 변경 내용

- project link는 다시 **prebuilt `tsn_icssg_combase` + local `tsn_icssg_gptp`** 조합으로 맞췄다.
- local `tsn_icssg_gptp`에 다음 계측을 추가했다.
  - `port_sync_sync_send_sm.c`
    - `port2_sync_gate:*`
    - `port2_sync_send:*`
  - `site_sync_sync_sm.c`
    - `site_sync_gate:*`

초기에는 `UBL_INFO` 레벨이라 trace에 잘 드러나지 않아, 이후 `site_sync_gate`/`port2_sync_gate`는 `ERR:gptp:`로 보이도록 상향했다.

### runtime 사실 1: `site_sync_sync`는 실제로 돈다

TMDS `trace0`에서 반복적으로 다음이 관측됐다.

```text
ERR:gptp:...:site_sync_gate:site_sync_sync_sm_portSyncSync domainIndex=0 srcPort=0
ERR:gptp:...:site_sync_gate:receiving_sync_proc allow=1 srcPort=0 srcSel=9 gmPresent=...
```

의미:

- `site_sync_sync_sm_portSyncSync()`는 실제 호출된다.
- `receiving_sync_proc allow=1`까지 간다.
- `srcSel=9`는 `SlavePort`다.
- 이 스택에서 `srcPort=0`은 synthetic/local clock master port 문맥과 맞물려 해석해야 한다.

즉 **site-sync 계층 자체는 정지 상태가 아니다.**

### runtime 사실 2: `port2` on-wire에는 Pdelay/Signaling은 보인다

SK `eth1` broad capture:

```text
vlan 0 + inner 0x88f7
msg type: peer delay req msg
msg type: peer delay resp msg
msg type: pdelay resp fup msg
msg type: signaling msg
```

반복 capture에서 `port2` 기준 on-wire로 보인 것은:

- `PdelayReq`
- `PdelayResp`
- `PdelayRespFollowUp`
- `Signaling`

### runtime 사실 3: `Sync/Follow_Up/Announce`는 여전히 안 보인다

- 같은 broad capture window에서 foreign `Sync` / `Follow_Up` / `Announce`는 계속 관측되지 않았다.
- `ptp4l eth1`는 다시 self-GM으로 끝났다.

```text
port 1 (eth1): LISTENING to MASTER on ANNOUNCE_RECEIPT_TIMEOUT_EXPIRES
selected local clock ... as best master
port 1 (eth1): assuming the grand master role
```

### runtime 사실 4: prebuilt baseline 특징도 그대로 유지된다

TMDS trace에는 여전히:

```text
stage=tx_evt state=count ... notify=95 / 172 ...
ERR:gptp:...:gptpnet_send:sent SIGNALING failed
```

즉

- real TX notify는 계속 온다.
- signaling failure 문자열도 계속 남아 있다.

### 가장 중요한 현재 해석

이 조합은 다음을 강하게 시사한다.

1. `port2` egress path 전체가 죽은 것은 아니다.
2. `port2`에서 **Pdelay / Signaling은 실제 wire로 나간다.**
3. 반면 `Sync / Follow_Up / Announce` 생성 경로만 열리지 않는다.
4. `site_sync_sync`는 살아 있으므로, 의심 지점은 더 좁혀져서:
   - `site_sync_sync -> portSyncSync_for_all()` 이후
   - `port_sync_sync_send_sm` early gate
   - `port_announce_transmit_sm`
   쪽이 된다.

특히 현재 가장 유력한 후보는:

- `port2`의 `AS_CAPABLE` 미성립
- 또는 그와 동급의 `port_sync_sync_send_sm` early gate 조건

근거:

- `Pdelay`/`Signaling`은 보이는데 `Sync/Announce`만 안 보인다.
- `port_sync_sync_send_sm`의 `allstate_condition()`은
  `!PORT_OPER || !PTP_PORT_ENABLED || !AS_CAPABLE`이면 send 상태로 진입하기 전에 잘라낸다.
- 현재까지 관측상 `PORT_OPER`은 살아 있을 가능성이 높고,
  `PTP_PORT_ENABLED`는 default true 설정이므로,
  **`AS_CAPABLE`가 가장 의심스럽다.**

### 현재 상태

- `port_sync_sync_send_sm`의 **`allstate block`** 계측까지 추가한 새 build는 완료했다.
- 다만 이 마지막 `allstate block` build는 아직 runtime 재부팅 검증 전이다.
- 따라서 `AS_CAPABLE=false`는 아직 **가장 강한 후보**이지, final proof는 아니다.

## 추가 검증: `allstate block` / `asCapable` 직접 trace 시도

### 적용한 추가 계측

- `port_sync_sync_send_sm.c`
  - `port2_sync_gate:allstate block ...`
- `gptpman.c`
  - `port2_ascap_eval ...`
  - `port2_ascap_update ...`
- `md_pdelay_req_sm.c`
  - `port2_ascross:set ...`
  - `port2_ascross:clear ...`

### 결과

- 최신 build를 TMDS에 재배포하고 override boot를 다시 수행했다.
- boot는 모두 `login:`까지 정상 도달했다.
- SK `eth1` broad capture에서는 여전히 아래만 관측됐다.
  - `PdelayReq`
  - `PdelayResp`
  - `PdelayRespFollowUp`
  - `Signaling`
- `ptp4l eth1`는 다시 self-GM으로 끝났다.

하지만 TMDS `trace0`에서는 이번 direct `asCapable` 관련 문자열이 **전혀 관측되지 않았다.**

```text
grep -E 'port2_ascap|port2_ascross' trace0 -> 0 hits
grep 'allstate block' trace0 -> 0 hits
```

반면 같은 런타임에서 여전히 보이는 것은:

```text
stage=tx_evt state=count ... notify=... 증가
```

### 해석 갱신

- 현재 증상 재현은 매우 안정적이다.
  - `port2`에는 `Pdelay`/`Signaling`만 보임
  - `Sync`/`Follow_Up`/`Announce`는 여전히 부재
  - `eth1`는 self-GM
- 다만 `UB_LOG` 기반의 library-level 추가 계측은 이번 경로에서 기대만큼 trace surface에 안정적으로 드러나지 않았다.

즉,

1. root-cause 후보는 계속
   - `site_sync -> downstream Sync/Announce generation`
   - `port_sync_sync_send_sm` early gate
   - `asCapable` 계열
   로 유지되지만,
2. **현재 trace channel만으로는 library 내부 조건값을 안정적으로 회수하기 어렵다.**

### 다음 분기

- 다음에는 `UB_LOG`가 아니라
  - app-adjacent hook에서 읽을 수 있는 상태를 끌어오거나
  - `RPROC_TRACE_*`로 직접 surface되는 경로에 상태 샘플을 싣는 방식
으로 바꿔야 한다.

## 추가 검증: app-side `ydbi_get_asCapable()` poll

### 변경 내용

- project `tsnapp_icssg_main.c`에 `App_traceGptpAsCapable()`를 추가했다.
- 이 hook은 1초마다 아래 값을 `RPROC_TRACE_INFO`로 직접 출력한다.

```c
ydbi_get_asCapable(ydbi_access_handle(), 0, 0, portIndex)
```

- 즉 library 내부 `UB_LOG`가 아니라, gPTP DB에 기록된 최종 `asCapable` 상태를 app에서 직접 읽는다.

### remoteproc 번호 주의

- boot마다 remoteproc 번호는 바뀐다.
- 이번 시점에서는 `78000000.r5f`가 `remoteproc1`이었다.
- 따라서 trace는 항상 `/sys/class/remoteproc/remoteproc*/name`으로 `78000000.r5f`를 찾은 뒤 대응하는 `trace0`를 읽어야 한다.

### 결과

`78000000.r5f`의 실제 trace0에서 반복 관측:

```text
[RPROC_TRACE] stage=gptp_port state=ascap code=0 port=1 asCap=0 macPort=1
[RPROC_TRACE] stage=gptp_port state=ascap code=0 port=2 asCap=0 macPort=2
```

즉 현재 이 runtime에서는:

- `port1 asCapable = 0`
- `port2 asCapable = 0`

가 계속 유지된다.

동시에 여전히 보이는 것은:

```text
stage=tx_evt state=count ... notify=...
ERR:gptp:...:gptpnet_send:sent SIGNALING failed
```

SK 쪽 결과도 동일했다.

- `eth1` slave는 계속 self-GM
- 이번 정확한 `remoteproc1` 상관 run에서는 `eth1` broad capture가 `0 packets captured`였지만,
  직전 반복 검증들에서는 `PdelayReq/Resp/FUP`와 `SIGNALING`만 보이고 `Sync/Follow_Up/Announce`는 계속 부재였다.

### 해석 갱신

이제는 다음을 강하게 말할 수 있다.

1. 문제는 `port2 downstream egress` 이전 단계다.
2. **gPTP port 자체가 asCapable로 올라가지 못한다.**
3. 따라서 `Sync/Announce` generation gate가 열리지 않는다.

현재 가장 타당한 구조적 해석은:

```c
if (ptd->mdeglb->forAllDomain->asCapableAcrossDomains &&
    (ptd->ppglb->neighborGptpCapable || is2011PdelayMsgCompatible))
```

이 조건의 좌변 또는 우변이 충족되지 않는다는 것이다.

구체적으로 남은 후보:

- `asCapableAcrossDomains`가 안 선다.
- `neighborGptpCapable`가 안 선다.
- `is2011BackwardCompatible`가 안 선다.

### 다음 분기

- 다음에는 local `gptp` library 쪽에서 `RPROC_TRACE`로 직접
  - `asCapableAcrossDomains`
  - `neighborGptpCapable`
  - `is2011BackwardCompatible`
  를 surface해서 어느 조건이 막는지 확정한다.

## 추가 검증: local `gptp`의 `asCapable` gate 내부값 직접 확인

### 변경 내용

- local `tsn_icssg_gptp`에 `RPROC_TRACE`를 추가했다.
  - `gptpman.c:set_asCapable()`
    - `stage=gptp_ascap state=eval`
    - `domain`, `port`, `across`, `neigh`, `compat2011`, `asCap`
  - `gptpman.c:update_asCapable_for_all()`
    - `stage=gptp_ascap state=update`
  - `md_pdelay_req_sm.c`
    - `stage=gptp_ascross state=set`
    - `stage=gptp_ascross state=clear`

### 주의

- 이번 boot에서도 `78000000.r5f`는 `remoteproc1`이었다.
- 따라서 판독은 `/sys/kernel/debug/remoteproc/remoteproc1/trace0` 기준으로 했다.

### 결정적 trace

```text
[RPROC_TRACE] stage=gptp_ascap state=eval code=0 domain=0 port=2 across=0 neigh=0 compat2011=1
```

반면 아래는 0건이었다.

```text
grep 'gptp_ascross' trace0 -> 0 hits
```

### 최종 판정

이제 `asCapable=0`의 직접 원인은 다음처럼 정리할 수 있다.

1. `asCapableAcrossDomains`는 `0`이다.
2. `neighborGptpCapable`는 `0`이다.
3. trace에서 `gptp_ascross`는 한 번도 관측되지 않았다.
4. 즉 `md_pdelay_req_sm`의 `asCapableAcrossDomains=true` 승격 경로가 실제로 열리지 않는다.
5. `gptp_ascap`에서 보인 `compat2011=1`은 참고 값이지만, 이 값만으로 실제 2011-compatible Pdelay completion이 정상 성립했다고 단정할 수는 없다.

이유:

- `md_pdelay_req_sm_init()`에서 `is2011BackwardCompatible`는 초기값이 `true`로 설정된다.

```c
(*sm)->is2011BackwardCompatible=true; // not receive any msg can be considered as true
```

따라서 현재 더 결정적인 사실은 `compat2011=1` 그 자체보다,
**`gptp_ascross`가 0 hits이고 `across=0`이 유지된다는 점**이다.

즉 최종 gate 실패는 다음처럼 요약된다.

1. `compat2011`은 현재 trace상 1로 보인다.
2. `neighborGptpCapable`는 `0`이다.
3. 그러나 결정적으로 **`asCapableAcrossDomains`가 0이라서 최종 gate가 절대 열리지 않는다.**
4. 따라서 `set_asCapable()` 조건:

```c
if (asCapableAcrossDomains && (neighborGptpCapable || is2011PdelayMsgCompatible))
```

에서 우변은 현재 `compat2011=1`로 보이므로 충족 가능성이 있지만,
좌변 `asCapableAcrossDomains=0` 때문에 최종 `asCapable`가 절대 올라가지 않는다.

즉 현재 문제의 직접 blocker는:

- **`md_pdelay_req_sm`에서 `asCapableAcrossDomains`가 set되는 경로가 열리지 않는 것**

이다.

### 남은 실제 수정 포인트

이제 남은 일은 원인 분석이 아니라 사실상 수정 포인트 확정에 가깝다.

- `md_pdelay_req_sm.c:waiting_for_pdelay_interval_timer_proc()`에서
  `asCapableAcrossDomains = true`로 승격되는 조건이 왜 성립하지 않는지 보정하거나,
- donor 의도와 Linux remoteproc 통합 사이의 차이 때문에 그 조건이 너무 보수적이면,
  현재 Path B 문맥에 맞는 최소 수정이 필요하다.

현재 가장 중요한 결론 한 줄:

- **문제는 `Sync/Announce` 생성이 아니라, 그보다 앞단인 `asCapableAcrossDomains` 미성립이다.**

## 결론

현재 시점의 최종 결론은 다음과 같다.

- **`gptp_icssg_switch` 예제는 현재 Path B Linux remoteproc 이식 상태에서는 donor와 동일한 기능으로 이식되지 않았다.**

판단 근거:

1. 반복 boot/traffic에서 SK `eth1` slave는 끝까지 self-GM이다.
2. wire-visible frame은 `PdelayReq/Resp/FUP`와 `SIGNALING`까지만 일부 보이지만,
   donor 의도 핵심인 downstream `Sync/Follow_Up/Announce`는 끝내 성립하지 않았다.
3. app-side DB poll로 `port1 asCap=0`, `port2 asCap=0`를 직접 확인했다.
4. local `gptp` gate trace로 `port=2 across=0 neigh=0 compat2011=1`을 직접 확인했다.
5. `gptp_ascross`는 0 hits였다.
   - 즉 `md_pdelay_req_sm`의 `asCapableAcrossDomains=true` 승격 경로가 실제로 열리지 않는다.
6. 이는 단순 문구 차이가 아니라,
   gPTP bridge-generated downstream sync path가 열리기 위한 prerequisite 자체가 성립하지 않는다는 뜻이다.

따라서 현재 repo의 Path B remoteproc port는 다음으로 분류한다.

- donor `gptp_icssg_switch`와 **behaviorally equivalent port 아님**
- remoteproc-hosted TSN/gPTP bring-up 실험 자산임
- 동일 기능을 원하면
  - `md_pdelay_req_sm` / `asCapableAcrossDomains` 승격 경로를 포함한
    deeper adaptation이 추가로 필요하다.

즉 이번 검증의 최종 outcome은 사용자 기준 2가지 중 후자다.
