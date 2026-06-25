# AM64x gPTP eth1 Lab Issues

## 현재까지 확인한 운영상 주의점

### 1. TMDS64EVM eth1이 부팅 직후 down일 수 있음

증상:

- `ip -br link show eth1`에서 `DOWN`
- `ethtool eth1`에서 `Link detected: no`

조치:

```bash
ip link set eth1 up
```

메모:

- direct gPTP 실험 전 고정 절차로 둔다.

### 2. PHC epoch가 wall clock와 다를 수 있음

증상:

- `date`는 2026년대인데 `phc_ctl /dev/ptp0 get`은 1970년대 표시
- `phc2sys` 초기 실행 시 비정상적으로 큰 offset 또는 step 실패

확인 명령:

```bash
date -Ins
phc_ctl /dev/ptp0 get
phc_ctl /dev/ptp0 cmp
```

MASTER 보드 조치:

```bash
phc_ctl /dev/ptp0 set
```

메모:

- 이번 세션에서는 SK-AM64B가 MASTER였으므로, SK의 PHC를 먼저 보정해야 했다.

### 3. phc2sys는 ptp4l 안정화 후 실행하는 편이 안전함

관찰:

- `ptp4l`이 `UNCALIBRATED -> SLAVE`로 충분히 안정화되기 전에 `phc2sys -w`를 실행하면
  과도 상태를 물고 비정상 offset이 보일 수 있었다.

권장 절차:

1. `ptp4l`이 `SLAVE` 상태에 진입하고 `rms/delay`가 안정되는지 확인
2. 이후 `phc2sys -s eth1 -c CLOCK_REALTIME -O 0 -m` 실행
