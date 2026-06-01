# 2026-06-01 SK-AM64B USB ROM Boot Driver Experiment

## 목적

SK-AM64B true USB ROM boot 시도에서 다음 SPL UART failure를 줄이기 위한
U-Boot driver-level rehearsal 변경을 기록한다.

```text
Trying to boot from USB
cdns-usb3-host usb@f400000: Couldn't get USB3 PHY: -19
Bus usb@f400000: Port not available.
No USB controllers found
0 Storage Device(s) found
SPL: Unsupported Boot Device!
```

## 변경 배경

이미 적용된 SPL DT override에서는 다음이 확인되었다.

- `ti,usb2-only`
- `dr_mode = "host"`
- `maximum-speed = "high-speed"`
- `phys` / `phy-names` 삭제

즉 DT 측면에서는 USB3 PHY dependency를 제거했는데도,
Cadence core driver가 여전히 `USB3 PHY: -19` 로 실패했다.

## 적용 변경

workspace 파일:

```text
workspace/ti-u-boot-sdk12/drivers/usb/cdns3/core.c
```

변경 요지:

```c
ret = generic_phy_get_by_name(dev, "cdns3,usb3-phy", &cdns->usb3_phy);
```

에서 missing optional PHY path로 판단되는 `-ENODEV` 를
fatal error가 아니라 skip 대상으로 취급한다.

diff 의미:

```text
before: ret != -ENOENT && ret != -ENODATA
after : ret != -ENOENT && ret != -ENODATA && ret != -ENODEV
```

## 의도

이 변경은 generic USB3 PHY path가 없는 `usb2-only` SPL USB boot rehearsal에서,
Cadence host core가 optional PHY absence를 fatal로 처리하지 않도록 하기 위한 것이다.

## 범위

- Linux kernel 변경 아님
- U-Boot SPL / USB host continuation 실험용 변경
- 정식 채택 전 실보드 UART 재검증 필요
