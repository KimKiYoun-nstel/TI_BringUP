# 테스트 절차

## 기본 동작 확인

`apply` 후 보드가 재부팅된 뒤 다음을 확인한다.

Phase 4 전체 정리 문서는 `docs/phase4-shm-vtm-summary.md`를 참고한다.

```bash
r5ctl ping
r5ctl status
r5ctl shm-status
r5ctl gpio list
r5ctl gpio get mcu_gpio0_8
r5ctl gpio get mcu_gpio0_6
r5ctl event get
r5ctl button status
r5ctl trace
```

정상 상태라면 다음이 보여야 한다.

- `service=rpmsg_chrdev`
- `endpoint=14`
- `shm_status`에서 `magic=0x52354653`, `version=0x00010000`, `seq` 증가
- output GPIO로 `mcu_gpio0_8 / MCU_GPIO0_8`
- input GPIO로 `mcu_gpio0_6 / MCU_GPIO0_6`
- active-low button state

## SHM status 확인

Phase 4 SHM slice는 **새 DTB가 먼저 부팅된 상태**에서만 확인해야 한다.

```bash
./tools/install/install-kernel-to-sd.sh 192.168.0.110 dtb-only --reboot
r5ctl shm-status
```

기대 결과:

```text
magic=0x52354653
version=0x00010000
seq=<n>
heartbeat=<증가>
shm_update_count=<증가>
linux_hwmon name=main0_thermal temp_millicelsius=<value>
linux_hwmon name=main1_thermal temp_millicelsius=<value>
```

2차 slice에서는 `soc_temp0_valid=1`, `soc_temp1_valid=1`이 기대값이다.
`soc_temp*_raw`는 10-bit raw code, `soc_temp*_millicelsius`는 Linux thermal driver와 같은 polynomial 기반 lookup 결과다.
실보드 기준으로는 Linux hwmon 대비 수백 mC 수준 차이는 허용 가능한 범위로 보고 delta를 함께 확인한다.

예시 검증 포인트:

```text
soc_temp0_valid=1
soc_temp1_valid=1
soc_temp0_delta_millicelsius ~= small negative/positive value
soc_temp1_delta_millicelsius ~= small negative/positive value
```

## GPIO output 테스트

```bash
r5ctl gpio set mcu_gpio0_8 1
r5ctl gpio get mcu_gpio0_8
r5ctl gpio set mcu_gpio0_8 0
r5ctl gpio get mcu_gpio0_8
```

기대 결과:

```text
RX: OK GPIO_SET gpio_id=mcu_gpio0_8 signal=MCU_GPIO0_8 value=1
RX: OK GPIO_GET ... value=1
RX: OK GPIO_SET gpio_id=mcu_gpio0_8 signal=MCU_GPIO0_8 value=0
RX: OK GPIO_GET ... value=0
```

가능하면 멀티미터 또는 외부 LED로 실제 전압 변화도 함께 확인한다.

## 버튼 이벤트 테스트

제한 시간 대기를 걸고 SW1을 눌렀다 뗀다.

```bash
r5ctl button wait 10000
```

기대 이벤트 형태:

```text
RX: GPIO_EVENT source=SW1 gpio_id=mcu_gpio0_6 signal=MCU_GPIO0_6 name=phase2_sw1 value=0 state=pressed edge=falling count=1 timestamp_us=<t>
```

연속 이벤트 확인 명령:

```bash
r5ctl event monitor
```

SW1을 여러 번 눌렀다 떼고, 다음과 같은 출력이 나오는지 본다.

```text
[001] GPIO_EVENT source=SW1 gpio_id=mcu_gpio0_6 signal=MCU_GPIO0_6 name=phase2_sw1 value=0 state=pressed edge=falling count=1 timestamp_us=<t>
[002] GPIO_EVENT source=SW1 gpio_id=mcu_gpio0_6 signal=MCU_GPIO0_6 name=phase2_sw1 value=1 state=released edge=rising count=2 timestamp_us=<t>
```

기존 회귀 확인이 필요하면 `r5ctl button monitor`도 동일하게 사용할 수 있다.

## Live-Board에서 수집할 증적

- `r5ctl status`
- `r5ctl shm-status`
- `r5ctl gpio list`
- `r5ctl gpio get mcu_gpio0_8`
- `r5ctl gpio set mcu_gpio0_8 1/0`
- SW1 누르기 전/후의 `r5ctl button status`
- pressed / released 이벤트가 보이는 `r5ctl event monitor`
- `[AM64X R5F PHASE3]` 로그가 보이는 `r5ctl trace`
- `/proc/iomem` 또는 boot log 기준 `r5f-status-shm@a5800000` reserved-memory 증적
- 필요 시 실제 booted image 기준 MCU GPIO ownership을 보여주는 pinctrl/debugfs 증적
