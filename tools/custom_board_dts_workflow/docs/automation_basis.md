# 자동화 근거

## 목적

이 문서는 워크플로우 안에서 어떤 단계까지 자동화 helper를 신뢰할 수 있는지 설명한다.

핵심은 다음 두 가지다.

1. `.NET`에서 board wiring 사실을 읽는다.
2. SysConfig DB에서 pad/signal/mux 근거를 읽는다.

이 두 입력이 만나는 지점까지만 helper를 강하게 신뢰한다.

## 입력과 역할

### 1. `.NET`

경로 예:

- `platforms/am64x/projects/<board-project>/inputs/netlist/*.NET`

이 입력에서 읽는 것:

- SoC refdes
- ball
- symbol pin 이름
- net 이름
- 연결된 외부 component/node

즉 `.NET`은 board-specific electrical connectivity의 기준이다.

### 2. SysConfig DB

경로 예:

- `platforms/am64x/db/am64x_sysconfig_pinmux_db.csv`

이 입력에서 읽는 것:

- ball
- signal_name
- interface_name
- mux_mode
- linux_macro
- dts_offset

즉 SysConfig DB는 특정 ball/signal이 DTS pinctrl에서 어떤 row가 되는지 검증하는 기준이다.

### 3. Reference DTS / Header

경로 예:

- `inputs/reference_dts/linux/*`
- `inputs/reference_dts/uboot/*`
- `inputs/reference_headers/*`

역할:

- SK-AM64B 같은 reference board 구조 비교
- header macro 참조
- candidate/base 층을 조립할 때 precedent 확인

중요:

- reference DTS는 fact source가 아니다.
- reference DTS는 integration precedent다.

## helper가 하는 일

1. `.NET` parse
2. SoC pin/net fact 추출
3. `ball + selected signal` 중심 SysConfig DB lookup
4. valid offset이 있는 pinmux만 facts 산출물 생성
5. reference DTS precedent와 기본 규칙으로 candidates 산출물 생성
6. facts + candidates를 조합해 base 산출물 생성

## 왜 facts 층은 신뢰 가능한가

`facts`는 다음 조건을 모두 만족하는 항목만 포함한다.

- `.NET`에서 SoC ball/net/signal이 확인됨
- SysConfig DB에서 대응 signal row가 식별됨
- `dts_offset`가 실제 값으로 존재함

즉 `facts`는 동일 입력이면 재생성 결과가 같아야 하는 층이다.

## 왜 candidates 층은 review 대상인가

`candidates`는 fact 위에 얹는 후보층이다.

- controller enable 후보
- device stub 후보
- U-Boot boot media 후보

이 층은 fact 자체를 바꾸지 않는다. 다만 reference precedent와 workflow 기본값을 이용하므로 최종 DTS로 바로 확정하지 않는다.

## 자동화에서 의도적으로 남겨둔 영역

다음은 현재 입력만으로는 확정되지 않으므로 사람이 review해야 한다.

- regulator / PMIC 정책
- PHY address / delay / `phy-mode`
- GPIO polarity
- DDR training / DDR include chain
- reserved-memory / remoteproc / memory size
- U-Boot `binman`, `bootph`, board-specific override

이 영역은 `manual_review_report.md`와 SK reference delta 문서를 보고 후속 통합한다.
실제 검토 순서는 `docs/review_checklist.md`를 따른다.

## 사용자 관점 핵심 출력

- `generated/linux/facts/*`
- `generated/linux/candidates/*`
- `generated/linux/base/*`
- `generated/uboot_spl/facts/*`
- `generated/uboot_spl/candidates/*`
- `generated/uboot_spl/base/*`
- `reports/facts/*`
- `reports/todo/manual_review_report.md`
- `projects/<board-project>/docs/sk_am64b_reference_delta_table.md`
