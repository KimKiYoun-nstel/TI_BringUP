# 테스트 절차

## Smoke Test

`apply` 후 보드가 재부팅된 뒤 다음을 확인한다.

```bash
r5ctl ping
r5ctl status
r5ctl button status
r5ctl trace
```

정상 상태라면 `service=rpmsg_chrdev`, `endpoint=14`, `button_gpio=MCU_GPIO0_6`, active-low button state가 보여야 한다.

## 버튼 이벤트 테스트

제한 시간 대기를 걸고 SW1을 눌렀다 뗀다.

```bash
r5ctl button wait 10000
```

기대 이벤트 형태:

```text
RX: BUTTON_EVENT source=SW1 gpio=MCU_GPIO0_6 value=0 state=pressed edge=falling count=1 timestamp_us=<t>
```

연속 이벤트 확인용:

```bash
r5ctl button monitor
```

SW1을 여러 번 눌렀다 떼고, 다음과 같은 출력이 나오는지 본다.

```text
[001] BUTTON_EVENT source=SW1 gpio=MCU_GPIO0_6 value=0 state=pressed edge=falling count=1 timestamp_us=<t>
[002] BUTTON_EVENT source=SW1 gpio=MCU_GPIO0_6 value=1 state=released edge=rising count=2 timestamp_us=<t>
```

## Live-Board에서 수집할 증적

- `r5ctl status`
- SW1 누르기 전/후의 `r5ctl button status`
- pressed / released 이벤트가 보이는 `r5ctl button monitor`
- `[AM64X R5F BUTTON]` 로그가 보이는 `r5ctl trace`
- 필요 시 실제 booted image 기준 MCU GPIO ownership을 보여주는 pinctrl/debugfs 증적
