# 2026-06-24 SK-AM64B SBL OSPI Linux Local-Fullchain Success

## 목적

이 문서는 SK-AM64B `SBL OSPI Linux`가 현재 repo 기준 `local-fullchain`
profile로 다시 boot 가능한 상태임을 짧게 고정한다.

## 이전 실패

이전 실패 signature:

```text
App_loadLinuxImages status=-1
Some tests have failed!!
```

## 이번에 정리된 핵심 보완점

1. `linux appimage` 입력 provenance를 `local-fullchain`으로 고정
2. `ATF_LOAD_ADDR`를 stale `0x701a0000` 대신 U-Boot 기준 `0x701c0000`으로 교정
3. `linuxAppimageGen`가 host `pyelftools 0.26`에서도 rebuild 되도록 compatibility patch 반영

## 이번 세션에서 board-side로 다시 확인한 것

clean canonical set의 OSPI readback hash:

`2026-06-25` 기준 source-bootstrap chain을 실제로 다시 돌린 뒤,
최종 verified set은 다음 hash로 갱신되었다.

- `SBL`: `54daa55a9368bc7a4037c11c306ee93be67161b92c46989cb88156b575b29c86`
- `R5F`: `8fe21f4561011ad3df73fde753588968193bc9cbe0a626782d8654b98e438a85`
- `U-Boot`: `3b21ef1da9fcbff4f28e565639c5ba885324ba4f66fa27d03fdf08c2b84cd74c`
- `linux appimage`: `5869d705b366694f30f3ef490bf8b02d8d9b99fe59bedeb6aef6c2cd2e2fcaea`

host artifact와 board-side readback hash가 일치했다.

## boot 결과 해석

raw UART capture 기준:

- `KPI_DATA: [BOOTLOADER PROFILE] App_loadLinuxImages              :      58325us`
- `Image loading done, switching to application ...`
- `Starting linux and RTOS/Baremetal applications`
- `Trying to boot from SPI`
- 이후 `BL31 -> OP-TEE -> U-Boot SPL -> U-Boot -> Linux` 진행

raw log file:

- `projects/sk-am64b-r5f-early-boot/logs/2026-06-25_sbl-ospi-linux-local-fullchain-source-bootstrap-uart.log`

즉 현재는 다음처럼 본다.

```text
LPDDR4 clean base + local-fullchain linux appimage lineage로
SK-AM64B SBL OSPI Linux boot가 다시 닫혔다.
```

## cleanup 후 현재 상태

failed-trial cleanup을 하면서 failure-only triage marker는 source에서 제거했고,
canonical build wrapper로 clean rebuild를 다시 만든 뒤,
그 clean set을 실제 OSPI에 write/reboot해서 Linux boot까지 재검증했다.

추가로 `2026-06-25`에는 source-bootstrap chain(TF-A, OP-TEE, clean U-Boot A53 worktree)을
실제로 다시 빌드한 뒤 동일 deploy chain으로 OSPI write/reboot 검증까지 완료했다.

## 비고

- `LINUX_MCELF_DIAG` marker는 failure-only triage용이라 성공 boot에서는 출력되지 않는 것이 정상이다.
- `Boot Media : undefined`는 profile 출력 문자열 문제로 보이며 이번 root cause의 핵심 증거는 아니다.
