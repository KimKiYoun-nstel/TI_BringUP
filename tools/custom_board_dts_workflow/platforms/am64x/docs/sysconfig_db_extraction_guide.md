# AM64x SysConfig 기반 DTS 생성용 Base DB 추출 가이드

## 목적

이 문서는 local Agent가 `~/ti/sysconfig_1.26.0`를 작업 root로 사용하여, TI SysConfig의 AM64x metadata에서 Linux/U-Boot DTS 생성에 필요한 base DB를 추출하도록 안내한다.

이번 작업은 DTS 자동 생성 Flow 2의 첫 단계다.

```text
Flow 2:
  Custom .NET
    -> custom board net facts 추출
  SysConfig AM64x metadata
    -> AM64x pinmux base DB 생성
  Linux DTS macro/header rule
    -> AM64X_IOPAD / AM64X_MCU_IOPAD 형식으로 변환
  결과
    -> SDK DTS에 없는 pinmux 조합도 검증 가능한 workflow helper 기반 준비
```

이번 가이드의 산출물은 최종 DTS가 아니라, DTS workflow helper가 사용할 **AM64x base DB**다.

---

## 작업 root

local Agent는 아래 경로를 root로 보고 작업한다.

```bash
cd ~/ti/sysconfig_1.26.0
```

현재 확인된 구조는 다음과 같다.

```text
~/ti/sysconfig_1.26.0/
  .metadata/
  dist/
    deviceData/
      AM64x/
        AM64x.json
        metadata.bundle
        templates/
        clocktree.json
  nodejs -> /home/nstel/ti/ccs2040/ccs/tools/node/
  sysconfig_cli.sh
  sysconfig_cli.bat
```

핵심 입력 파일은 다음 두 개다.

```text
dist/deviceData/AM64x/AM64x.json
dist/deviceData/AM64x/metadata.bundle
```

---

## 현재까지 확인된 SysConfig metadata 구조

`AM64x.json`의 top-level key는 다음과 같다.

```text
rowColumnInverted
cores
interfacePins
interfaces
useCases
powerDomains
devicePins
peripheralPins
peripherals
parts
packages
reverseMuxes
pinCommonInfos
muxes
```

DTS pinmux DB 생성에 직접 필요한 key는 다음이다.

| Key | 용도 |
|---|---|
| `packages` | package `ALV`, `devicePinID -> ball` 매핑 |
| `devicePins` | `devicePinID -> device pin name` 매핑 |
| `peripheralPins` | `peripheralPinID -> peripheral signal name` 매핑 |
| `pinCommonInfos` | `devicePinID -> controlRegisterOffset`, mode별 signal 정보 |
| `muxes` | `devicePinID -> peripheralPinID -> mux mode` 관계 |
| `reverseMuxes` | `peripheralPinID -> devicePinID -> mux mode` 역방향 관계 |

`metadata.bundle`에는 Linux DTS 템플릿이 포함되어 있다.

```text
/AM64x/templates/linux/devicetree.dtsi.xdt
```

이 템플릿은 SysConfig가 Linux device tree fragment를 생성할 때 사용하는 XDT template이다. Agent는 이 파일을 참고하여 MAIN/WKUP/MCU domain 분리 방식, offset 출력 방식, DTS pinctrl 출력 포맷을 확인해야 한다.

---

## 생성해야 할 산출물

Agent는 작업 root 아래에 다음 구조를 생성한다.

```text
out_dts_db/
  am64x_sysconfig_pinmux_db.csv
  am64x_sysconfig_pinmux_db.json
  am64x_package_pins.csv
  am64x_pin_common_infos.csv
  am64x_linux_dt_template.txt
  extraction_report.md
  validation_report.md

scripts/
  extract_am64x_sysconfig_db.py
```

최소 필수 산출물은 다음 네 개다.

```text
out_dts_db/am64x_sysconfig_pinmux_db.csv
out_dts_db/am64x_sysconfig_pinmux_db.json
out_dts_db/extraction_report.md
out_dts_db/validation_report.md
```

---

## 최종 DB 스키마

### 1. `am64x_sysconfig_pinmux_db.csv`

필수 column:

```csv
soc,package,ball,device_pin_id,device_pin_name,control_register_offset,interface_name,signal_name,peripheral_pin_id,peripheral_pin_name,mux_mode,io_dir,power_domain_id,domain,linux_macro,dts_offset,source
```

각 column 의미:

| Column | 설명 |
|---|---|
| `soc` | 고정값 `AM64x` |
| `package` | 현재는 `ALV` |
| `ball` | SoC package ball, 예: `D15`, `A18` |
| `device_pin_id` | SysConfig 내부 devicePinID |
| `device_pin_name` | SysConfig device pin name |
| `control_register_offset` | SysConfig `pinCommonInfos[*].controlRegisterOffset` |
| `interface_name` | 예: `UART0`, `I2C0`, `MCU_UART0`, `GPIO1` |
| `signal_name` | 예: `UART0_RXD`, `I2C0_SCL` |
| `peripheral_pin_id` | SysConfig 내부 peripheralPinID |
| `peripheral_pin_name` | `peripheralPins[peripheral_pin_id].name` |
| `mux_mode` | mux mode 값, 문자열 또는 정수 |
| `io_dir` | SysConfig `ioDir`; 비어있을 수 있음 |
| `power_domain_id` | package pin의 powerDomainID |
| `domain` | `MAIN` 또는 `MCU_WKUP` |
| `linux_macro` | `AM64X_IOPAD` 또는 `AM64X_MCU_IOPAD` |
| `dts_offset` | DTS macro에 넣을 offset. 기본적으로 `control_register_offset` 사용 |
| `source` | `sysconfig:dist/deviceData/AM64x/AM64x.json` |

### 2. `am64x_sysconfig_pinmux_db.json`

CSV와 동일한 정보를 JSON list로 저장한다. 후속 DTS workflow helper는 JSON을 주 입력으로 사용할 수 있다.

예상 record 예시:

```json
{
  "soc": "AM64x",
  "package": "ALV",
  "ball": "D15",
  "device_pin_id": "ID_3125",
  "device_pin_name": "UART0_RXD",
  "control_register_offset": "0x0230",
  "interface_name": "UART0",
  "signal_name": "UART0_RXD",
  "peripheral_pin_id": "...",
  "peripheral_pin_name": "UART0_RXD",
  "mux_mode": "0",
  "io_dir": "I",
  "power_domain_id": "ID_3088",
  "domain": "MAIN",
  "linux_macro": "AM64X_IOPAD",
  "dts_offset": "0x0230",
  "source": "sysconfig:dist/deviceData/AM64x/AM64x.json"
}
```

---

## 추출 로직

### Step 1. 입력 JSON 로드

```python
import json
from pathlib import Path

ROOT = Path(".")
am64x = json.loads((ROOT / "dist/deviceData/AM64x/AM64x.json").read_text())
metadata = json.loads((ROOT / "dist/deviceData/AM64x/metadata.bundle").read_text())
```

### Step 2. package ball map 생성

`packages`에는 ALV package의 `devicePinID -> ball` 정보가 있다.

```python
packages = am64x["packages"]
# 현재 AM64x는 packages dict len == 1, first package name == ALV
pkg = next(iter(packages.values()))
package_name = pkg["name"]

ball_map = {}
for p in pkg["packagePin"]:
    ball_map[p["devicePinID"]] = {
        "ball": p.get("ball", ""),
        "power_domain_id": p.get("powerDomainID", ""),
    }
```

### Step 3. device pin / peripheral pin map 생성

```python
device_pins = am64x["devicePins"]
peripheral_pins = am64x["peripheralPins"]
```

- `devicePins[devicePinID]["name"]`을 `device_pin_name`으로 사용한다.
- `peripheralPins[peripheralPinID]["name"]`을 `peripheral_pin_name`으로 사용한다.

### Step 4. pinCommonInfos를 기준으로 flatten

가장 중요한 정보는 `pinCommonInfos`다.

```python
for device_pin_id, common in am64x["pinCommonInfos"].items():
    offset = common.get("controlRegisterOffset", "")
    mode_infos = common.get("pinModeInfo", [])
    for mi in mode_infos:
        peripheral_pin_id = mi.get("peripheralPinID", "")
        mode = mi.get("mode", "")
        interface_name = mi.get("interfaceName", "")
        signal_name = mi.get("signalName", "")
        io_dir = mi.get("ioDir", "")
```

각 `pinModeInfo` 항목이 pinmux DB의 한 row가 된다.

---

## domain / linux macro 결정 규칙

SysConfig Linux DTS template은 assignment의 interface name에 `WKUP` 또는 `MCU`가 들어가는지, 또는 일부 예외 pin인지에 따라 MAIN과 WKUP/MCU 그룹을 나눈다.

Agent는 1차 DB에서 다음 단순 규칙을 사용한다.

```python
def classify_domain(interface_name, signal_name, device_pin_name):
    text = f"{interface_name} {signal_name} {device_pin_name}".upper()
    wkup_exc = {
        "TDI", "TDO", "PMIC_POWER_EN1", "TCK", "TMS", "TRSTN",
        "EMU0", "EMU1", "PORZ",
    }
    if "MCU" in text or "WKUP" in text:
        return "MCU_WKUP", "AM64X_MCU_IOPAD"
    if signal_name.upper() in wkup_exc or device_pin_name.upper() in wkup_exc:
        return "MCU_WKUP", "AM64X_MCU_IOPAD"
    return "MAIN", "AM64X_IOPAD"
```

주의:

- 이 규칙은 1차 추정이다.
- 정확한 분리는 `metadata.bundle`의 `/AM64x/templates/linux/devicetree.dtsi.xdt` 로직과 비교 검증한다.
- 검증 결과는 `validation_report.md`에 남긴다.

---

## dts_offset 결정 규칙

1차 DB에서는 다음처럼 처리한다.

```python
dts_offset = control_register_offset
```

이유:

- SysConfig `pinCommonInfos[*].controlRegisterOffset`가 이미 DTS template의 `assignment.devicePin.controlRegisterOffset`로 사용되는 값으로 보인다.
- Linux DTS template의 `getOffset()` 함수가 이 값을 어떤 방식으로 가공하는지 반드시 확인해야 한다.

Agent는 `metadata.bundle`에서 Linux DTS template을 `out_dts_db/am64x_linux_dt_template.txt`로 저장하고, `getOffset()` 함수 부분을 추출하여 `validation_report.md`에 기록한다.

확인 명령 예:

```bash
python3 - <<'PY'
import json
m=json.load(open("dist/deviceData/AM64x/metadata.bundle"))
t=m["/AM64x/templates/linux/devicetree.dtsi.xdt"]
for i,line in enumerate(t.splitlines(), 1):
    if "var getOffset" in line or "controlRegisterOffset" in line or "AM64" in line or "IOPAD" in line:
        print(i, line)
PY
```

---

## 추출 스크립트 요구사항

Agent는 `scripts/extract_am64x_sysconfig_db.py`를 작성한다.

스크립트 실행 방식:

```bash
cd ~/ti/sysconfig_1.26.0
python3 scripts/extract_am64x_sysconfig_db.py
```

스크립트는 다음을 수행한다.

1. `dist/deviceData/AM64x/AM64x.json` 로드
2. `dist/deviceData/AM64x/metadata.bundle` 로드
3. `out_dts_db/` 생성
4. ALV package의 `devicePinID -> ball/powerDomainID` 추출
5. `pinCommonInfos`를 flatten하여 pinmux DB 생성
6. CSV/JSON 저장
7. Linux DTS template 저장
8. extraction report 생성
9. validation report 생성

---

## 검증 기준

Agent는 DB 생성 후 다음 sanity check를 수행한다.

### 1. row count

기대값:

```text
devicePins: 441
pinCommonInfos: 441
peripheralPins: 1079
pinmux DB rows: 1079 근처 또는 그 이상/이하 가능
```

`pinmux DB rows`는 `pinCommonInfos[*].pinModeInfo` 전체 개수다.

### 2. 필수 signal lookup

다음 signal은 반드시 DB에서 검색되어야 한다.

```text
UART0_RXD
UART0_TXD
I2C0_SCL
I2C0_SDA
I2C1_SCL
I2C1_SDA
MCU_UART0_RXD
MCU_UART0_TXD
```

기대 매핑 예시:

```text
D15 -> UART0_RXD -> offset 0x0230 -> mode 0 -> AM64X_IOPAD
C16 -> UART0_TXD -> offset 0x0234 -> mode 0 -> AM64X_IOPAD
A18 -> I2C0_SCL  -> offset 0x0260 -> mode 0 -> AM64X_IOPAD
B18 -> I2C0_SDA  -> offset 0x0264 -> mode 0 -> AM64X_IOPAD
C18 -> I2C1_SCL  -> offset 0x0268 -> mode 0 -> AM64X_IOPAD
B19 -> I2C1_SDA  -> offset 0x026c -> mode 0 -> AM64X_IOPAD
A9  -> MCU_UART0_RXD -> AM64X_MCU_IOPAD 후보
A8  -> MCU_UART0_TXD -> AM64X_MCU_IOPAD 후보
```

위 기대 매핑은 SDK DTS 및 회로도/netlist에서 이미 검토한 대표 항목이다. 실제 DB 값과 다르면 `validation_report.md`에 mismatch로 기록한다.

### 3. SDK DTS cross-check

가능하면 local SDK의 기존 DTS와 비교한다.

대상 DTS 예:

```text
~/ti/am64x/.../ti-linux-kernel.../arch/arm64/boot/dts/ti/k3-am642-sk.dts
```

확인 대상:

```text
AM64X_IOPAD(0x0230, ..., 0) /* (D15) UART0_RXD */
AM64X_IOPAD(0x0234, ..., 0) /* (C16) UART0_TXD */
AM64X_IOPAD(0x0260, ..., 0) /* (A18) I2C0_SCL */
AM64X_IOPAD(0x0264, ..., 0) /* (B18) I2C0_SDA */
```

SysConfig DB와 SDK DTS 값이 일치하면 `validation_report.md`에 `PASS`로 기록한다.

---

## 생성된 DB를 이용한 DTS pinmux 생성 예

DB lookup 입력:

```text
ball = D15
signal = UART0_RXD
```

DB lookup 결과:

```text
control_register_offset = 0x0230
mux_mode = 0
linux_macro = AM64X_IOPAD
io_dir = I 또는 input 후보
```

DTS pinctrl line 후보:

```dts
AM64X_IOPAD(0x0230, PIN_INPUT, 0) /* (D15) UART0_RXD */
```

DB lookup 입력:

```text
ball = A18
signal = I2C0_SCL
```

DTS pinctrl line 후보:

```dts
AM64X_IOPAD(0x0260, PIN_INPUT_PULLUP, 0) /* (A18) I2C0_SCL */
```

주의:

- `PIN_INPUT`, `PIN_OUTPUT`, `PIN_INPUT_PULLUP` 같은 flag 결정은 pinmux DB만으로 100% 확정하지 않는다.
- 기본값은 `io_dir`와 peripheral-specific rule로 생성한다.
- I2C는 open-drain이므로 `PIN_INPUT_PULLUP` 후보로 처리한다.
- 최종 flag rule은 다음 단계에서 `k3-pinctrl.h`, SDK DTS corpus, peripheral rule DB로 보강한다.

---

## Agent가 작성할 Python 스크립트 예시 골격

```python
#!/usr/bin/env python3
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AM64X_JSON = ROOT / "dist/deviceData/AM64x/AM64x.json"
METADATA_BUNDLE = ROOT / "dist/deviceData/AM64x/metadata.bundle"
OUT = ROOT / "out_dts_db"

WKUP_EXC = {
    "TDI", "TDO", "PMIC_POWER_EN1", "TCK", "TMS", "TRSTN",
    "EMU0", "EMU1", "PORZ",
}

FIELDS = [
    "soc", "package", "ball", "device_pin_id", "device_pin_name",
    "control_register_offset", "interface_name", "signal_name",
    "peripheral_pin_id", "peripheral_pin_name", "mux_mode", "io_dir",
    "power_domain_id", "domain", "linux_macro", "dts_offset", "source",
]


def classify_domain(interface_name, signal_name, device_pin_name):
    text = f"{interface_name} {signal_name} {device_pin_name}".upper()
    if "MCU" in text or "WKUP" in text:
        return "MCU_WKUP", "AM64X_MCU_IOPAD"
    if signal_name.upper() in WKUP_EXC or device_pin_name.upper() in WKUP_EXC:
        return "MCU_WKUP", "AM64X_MCU_IOPAD"
    return "MAIN", "AM64X_IOPAD"


def main():
    OUT.mkdir(exist_ok=True)

    data = json.loads(AM64X_JSON.read_text())
    metadata = json.loads(METADATA_BUNDLE.read_text())

    packages = data["packages"]
    package = next(iter(packages.values()))
    package_name = package.get("name", "UNKNOWN")

    ball_map = {}
    for pin in package.get("packagePin", []):
        ball_map[pin["devicePinID"]] = {
            "ball": pin.get("ball", ""),
            "power_domain_id": pin.get("powerDomainID", ""),
        }

    device_pins = data["devicePins"]
    peripheral_pins = data["peripheralPins"]
    pin_common_infos = data["pinCommonInfos"]

    rows = []
    missing_ball = 0
    for device_pin_id, common in pin_common_infos.items():
        device_pin = device_pins.get(device_pin_id, {})
        device_pin_name = device_pin.get("name", "")
        offset = common.get("controlRegisterOffset", "")
        ball_info = ball_map.get(device_pin_id, {})
        ball = ball_info.get("ball", "")
        power_domain_id = ball_info.get("power_domain_id", "")
        if not ball:
            missing_ball += 1

        for mode_info in common.get("pinModeInfo", []):
            peripheral_pin_id = mode_info.get("peripheralPinID", "")
            peripheral_pin = peripheral_pins.get(peripheral_pin_id, {})
            interface_name = mode_info.get("interfaceName", "")
            signal_name = mode_info.get("signalName", "")
            io_dir = mode_info.get("ioDir", "")
            domain, macro = classify_domain(interface_name, signal_name, device_pin_name)

            rows.append({
                "soc": "AM64x",
                "package": package_name,
                "ball": ball,
                "device_pin_id": device_pin_id,
                "device_pin_name": device_pin_name,
                "control_register_offset": offset,
                "interface_name": interface_name,
                "signal_name": signal_name,
                "peripheral_pin_id": peripheral_pin_id,
                "peripheral_pin_name": peripheral_pin.get("name", ""),
                "mux_mode": mode_info.get("mode", ""),
                "io_dir": io_dir,
                "power_domain_id": power_domain_id,
                "domain": domain,
                "linux_macro": macro,
                "dts_offset": offset,
                "source": "sysconfig:dist/deviceData/AM64x/AM64x.json",
            })

    with (OUT / "am64x_sysconfig_pinmux_db.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)

    (OUT / "am64x_sysconfig_pinmux_db.json").write_text(json.dumps(rows, indent=2))

    # Auxiliary outputs
    with (OUT / "am64x_package_pins.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["device_pin_id", "ball", "power_domain_id"])
        w.writeheader()
        for k, v in sorted(ball_map.items()):
            w.writerow({"device_pin_id": k, **v})

    dt_key = "/AM64x/templates/linux/devicetree.dtsi.xdt"
    if dt_key in metadata:
        (OUT / "am64x_linux_dt_template.txt").write_text(metadata[dt_key])

    report = []
    report.append("# AM64x SysConfig DB Extraction Report")
    report.append("")
    report.append(f"- package: {package_name}")
    report.append(f"- devicePins: {len(device_pins)}")
    report.append(f"- peripheralPins: {len(peripheral_pins)}")
    report.append(f"- pinCommonInfos: {len(pin_common_infos)}")
    report.append(f"- generated rows: {len(rows)}")
    report.append(f"- missing ball rows by device pin: {missing_ball}")
    report.append("")
    report.append("## Notes")
    report.append("")
    report.append("- This DB is generated from SysConfig AM64x metadata, not from PDF parsing.")
    report.append("- Datasheet/TRM should be used later for official cross-check.")
    (OUT / "extraction_report.md").write_text("\n".join(report))

    targets = [
        "UART0_RXD", "UART0_TXD", "I2C0_SCL", "I2C0_SDA",
        "I2C1_SCL", "I2C1_SDA", "MCU_UART0_RXD", "MCU_UART0_TXD",
    ]
    val = ["# AM64x SysConfig DB Validation Report", ""]
    for t in targets:
        hits = [r for r in rows if r["signal_name"] == t or r["peripheral_pin_name"] == t]
        val.append(f"## {t}")
        if not hits:
            val.append("- result: MISSING")
        else:
            val.append(f"- result: FOUND ({len(hits)} hit(s))")
            for r in hits[:8]:
                val.append(
                    f"- ball={r['ball']}, offset={r['control_register_offset']}, "
                    f"mode={r['mux_mode']}, interface={r['interface_name']}, "
                    f"macro={r['linux_macro']}, ioDir={r['io_dir']}"
                )
        val.append("")
    (OUT / "validation_report.md").write_text("\n".join(val))

    print(f"Generated {len(rows)} rows")
    print(f"Output: {OUT}")


if __name__ == "__main__":
    main()
```

---

## Agent 작업 완료 기준

Agent는 다음을 완료해야 한다.

1. `scripts/extract_am64x_sysconfig_db.py` 생성
2. 스크립트 실행 성공
3. `out_dts_db/am64x_sysconfig_pinmux_db.csv` 생성
4. `out_dts_db/am64x_sysconfig_pinmux_db.json` 생성
5. `validation_report.md`에서 필수 signal 8개가 FOUND인지 확인
6. `D15 UART0_RXD`, `C16 UART0_TXD`, `A18 I2C0_SCL`, `B18 I2C0_SDA`의 offset/mode가 SDK DTS와 맞는지 확인
7. 결과 요약을 `out_dts_db/extraction_report.md`에 기록

---

## 다음 단계

이 DB가 생성되면 다음 작업은 `.NET` parser와 join하는 것이다.

```text
CPU_BRD_V03_PBA_260511.NET
  -> U1 ball / signal / net 추출

am64x_sysconfig_pinmux_db.csv
  -> ball + signal 기준 lookup

결과
  -> generated pinmux dtsi
```

즉 다음 단계 산출물은 다음이 된다.

```text
custom_board_net_facts.csv
custom_board_pinmux_lookup.csv
k3-am6412-custom-pinmux.dtsi
pinmux_lookup_validation_report.md
```
