# SK-AM64B R5F Early Boot Plan

## 목적

이 문서는 `projects/sk-am64b-r5f-early-boot/` 아래에서
현재 실험의 큰 그림과 작업 단위별 진입 상태를 한 눈에 볼 수 있게 정리한다.

## 현재 작업 단위

현재는 다음 상태다.

```text
task-unit-1 : closeout 완료
task-unit-2 : local-fullchain canonical profile 확정 + OSPI Linux boot 재확인
task-unit-3 : 후속 behavior 정합성만 남음
```

## task-unit-1

- 결과 문서: `docs/task1-inventory-result.md`
- 핵심 판단: local kernel attach / IPC-only 흔적 존재
- gate: `Gate 1-A`

## task-unit-2

현재까지 정리된 축:

- heartbeat minimal feature spec
- heartbeat SHM ABI draft
- heartbeat first draft source
- heartbeat local buildable draft 확인
- R5F / Linux local image generation path 확인
- Linux appimage input inventory
- SPL naming / staging mapping
- linux appimage staging dry-run helper
- LPDDR4 DDR reginit root-cause 정리
- local-fullchain canonical build profile 정리
- current OSPI success log 확보

실행 순서 정리 문서:

- `docs/phase2-execution-checklist.md`

## task-unit-3

다음 집중 항목:

- custom early-boot R5F firmware heartbeat/SHM behavior 확인
- custom A53 checker app으로 early-boot firmware 동작 확인
- 이후 own RPMsg app-to-app transport 정합성 확인
- 위 항목은 현재 project 내부 follow-up으로만 유지

현재 단계 계획:

```text
M1 : SHM으로 R5F early-boot 동작 확인
M2 : early-boot firmware에 RPMsg endpoint bring-up 추가
M3 : own app protocol 확장
```

현재 M1 후속 확인 필요:

- `early_heartbeat_status.h`의 SHM base `0xA5800000`
- generated SysConfig/linker shared-memory region (`0xA5000000` 계열)
- generated MPU non-cached region도 `0xA0000000` / `0xA5000000` 계열 기준
- draft runtime code에는 cache maintenance 호출이 없음
- `0xA5800000`은 DT inventory 기준 기존 `rtos_ipc_memory_region` 끝(`0xA57FFFFF`)의 바로 다음 주소
- working reference (`am64x-r5f-button-event-lab`)는 `0xA5800000`을 위해 별도 non-cached MPU region + DT reserved-memory를 명시함

즉 현재는

```text
heartbeat SHM base 상수
vs
generated shared-memory/cacheability model
```

사이의 불일치 가능성을 우선 확인해야 한다.

결과:

```text
button-event-lab reference의 0xA5800000 non-cached MPU region을
current draft syscfg에 반영한 뒤,
current-source appimage를 clean reflashing 하자 M1 SHM checker가 PASS로 전환되었다.
```

상세 계획 문서:

- `docs/communication-plan.md`

중요:

```text
boot-chain 자체는 현재 local-fullchain profile 기준으로 다시 닫혔다.
남은 것은 firmware/application behavior 정합성 후속 작업이다.
```

현재 canonical build/flash 기준:

- `docs/sbl-ospi-linux-local-fullchain-profile.md`
- `bsp/mcu-plus/configs/sbl_ospi_linux_sk-am64b_local-fullchain.cfg`
- `tools/build/build-sk-am64b-sbl-ospi-linux-local-fullchain.sh`

## repo-wide reusable assets

- `sdk-manifest/*`
- `bsp/mcu-plus/notes/*`
- `tools/build/*`
- `tools/install/*`
- `logs/provenance/*`
