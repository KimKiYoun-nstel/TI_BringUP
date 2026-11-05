# UART daemon 기반 Agent 작업 절차

## 현재 구조

2026-11-05부터 현 Ubuntu workspace는 `192.168.0.33`의 UART daemon을 TCP로 사용한다.
UART 물리 포트의 소유자는 해당 서버의 `uartd`다.

MCP server는 repo별로 독립 구성한다. 이 repo의 `tools/uart/integration/mcp_server.py`는
공식 `official/python/uart_api.py`를 통해 원격 daemon과 통신하고 보드 선택 및 bring-up 도구를 제공한다.
공식 `official/python/uart_mcp.py`와 MCP 매뉴얼은 UART 호출을 MCP로 노출하는 참고 예제다.
공식 코드·문서는 ZIP 없이 Git source/docs로 관리하며,
갱신은 [공식 UART 배포본 갱신 절차](../../tools/uart/UPGRADING.md)를 따른다.
공식 소스·문서는 `official/{python,manuals}/`, repo 전용 wrapper·MCP는 `integration/`에 둔다.
파일 해시 관리는 하지 않는다.

| target | 보드 | endpoint | 확인된 UART |
|---|---|---|---|
| `sk` | SK-AM64B | `192.168.0.33:17001` | COM10 / 115200 |
| `tmds` | TMDS64EVM | `192.168.0.33:17002` | COM7 / 115200 |

보드의 Boot ROM → SPL → U-Boot → Linux → service/application 흐름을 같은 daemon 세션으로
관찰한다. UART 접속 자체를 위해 현 장비에서 serial port를 직접 열지 않는다.
COM 번호는 조회 시점의 값이며 재연결 후 `uart_list_ports`/`uart_status`로 확인한다.

## 먼저 확인할 것

1. 의도한 target을 명시해 `uart_status`를 조회한다.
2. `serial_state=connected`, 실제 `port`, `baud`, `instance_id`를 확인한다.
3. `uart_tail`로 최근 콘솔 상태를 확인한다.
4. U-Boot는 `=> `, Linux root는 `# `, 로그인 대기는 `login:`을 기준으로 판단한다.
5. 현재 boot 단계와 맞는 명령을 실행한다. 오래된 prompt만으로 현재 상태를 단정하지 않는다.

```text
uart_status(target="sk")
uart_tail(target="sk", lines=80)
uart_command(target="sk", line="uname -a", expect="# ", timeout=10, newline="lf")
```

두 보드의 endpoint/token/session은 서로 다르다. 기본 target은 SK이지만 여러 보드를 다루는 작업은
모든 호출에 target을 명시한다. 현재 `custom` target은 배정되어 있지 않다.

## MCP 설정과 인증

- `opencode.jsonc`: `mcp.uart` → `/usr/bin/python3 ./tools/uart/integration/mcp_server.py`.
- `tools/uart/config/targets.json`: endpoint와 target별 토큰 파일 경로.
- `tools/uart/.secrets/{sk,tmds}.token`: Git 제외, 로컬에서만 보관하는 서버 인증 토큰.
- Python 표준 라이브러리 기반 repo adapter를 사용하므로 FastMCP 설치는 필요하지 않다.

repo 루트에서 OpenCode를 실행한다. 설정 변경은 실행 중 세션에 hot reload되지 않으므로 종료 후
재시작한다. 재시작 후 `tools/list`에 UART tool 11개가 보이는지 확인한다.
토큰 선택 우선순위와 새 장비 준비는 [UART 도구 가이드](../../tools/uart/README.md)를 따른다.

## 입력과 출력 대기

- 일반 명령: `uart_command(line=..., expect=...)`. 한 요청에서 명령 전송 이후 출력만 기다린다.
- 입력만 전송: `uart_sendline(line=...)`.
- 개행 없이 raw 입력: `uart_send(text=..., newline=false)`. Ctrl-C 등은 실제 제어 문자를 전달한다.
- 출력만 대기: `uart_expect(pattern=..., from="now")`.
- 이미 도착한 출력 검색: `uart_expect(pattern=..., from="buffer")`.
- 특정 이후 구간 검색: `from_offset`을 사용한다. offset은 daemon의 문자 위치다.

pattern은 정규식이 아닌 리터럴 부분 문자열이다. `uart_sendline`/`uart_command`의 개행은
`lf`, `crlf`, `cr`, `none` 중 선택한다. 현재 MCP 설정의 기본 개행은 LF다.
배포 FastMCP와 달리 repo의 `uart_command` 인자는 `text`가 아닌 **`line`**이다.

timeout은 명령이 실행되지 않았다는 의미가 아니다. 같은 명령을 반복하지 말고 `uart_tail`로 최근
출력을 확인한 뒤 다음 동작을 결정한다. 별도 send → expect 사이에 prompt가 이미 도착할 수 있으므로
일반 명령은 `uart_command`를 우선 사용한다.

## 연결 상태와 포트 변경

신버전 daemon은 UART가 없어도 TCP 제어 연결을 유지할 수 있다.

- `status.ok=true`는 daemon 응답 성공이다. `serial_state`, `port`, `last_serial_error`를 함께 본다.
- `uart_list_ports`: 서버 호스트의 serial 장치를 조회한다.
- `uart_set_port(port=..., baud=..., force=false)`: daemon 재시작 없이 포트를 연결/전환한다.
- `uart_disconnect(force=false)`: UART만 해제하며 daemon과 TCP는 유지한다.
- `uart_baud(baud=...)`: 현재 연결의 baud를 바꾼다.

이 동작들은 해당 daemon을 공유하는 모든 client에 영향을 준다. RW attach가 있으면 포트 전환이
거절되며, 전환이 의도된 경우에만 `force=true`를 사용한다. expect/command 진행 중에는 완료 후
다시 시도한다. 새 포트 열기에 실패하면 기존 연결을 보존한다.
`session_generation`이 바뀌면 새 연결 세션으로 구분하고 이전 검색 buffer와 혼동하지 않는다.

`rw_attach_clients`, `ro_attach_clients`, `last_writer`로 공유 상태를 확인한다.
공식 신규 daemon은 `send_expect`에 기본 exclusive lease를 사용한다. RW attach가 있거나
다른 command가 실행 중이면 command 시작을 거절하므로, 사용을 마친 RW attach를 먼저 종료한다.
RO 모니터링은 가능하다. 실제 적용 동작은 원격 daemon 버전을 기준으로 확인한다.

## reboot → U-Boot

`uart_reboot_to_uboot`는 Linux shell/login 상태 확인, reboot, autoboot 중단, U-Boot prompt 대기를
한 흐름으로 처리하는 기존 helper다. 실제 reboot가 필요한 작업에서 사용한다.
실패하면 `uart_tail`로 마지막 boot 단계와 prompt를 확인하고 같은 reboot를 무조건 반복하지 않는다.
보드별 autoboot 문구가 다르면 helper 인자를 조정한다.

## UART 증적의 기준

기준은 **선택한 target의 daemon이 기록한 `runtime_log`**다.
`uart_status.runtime_log`는 서버 파일 경로이며 현재는 원격 Windows 경로다.
현 Ubuntu의 `logs/runtime_log`는 자동 동기화되지 않는다.

- 원격 작업은 같은 target의 `uart_tail` 또는 CLI `tail`/`watch`를 우선 증적으로 사용한다.
- 로컬 `logs/runtime_log`가 있으면 대상 보드/수집 시점이 일치하는 링크 또는 복사본인지 확인한다.
- 로그를 장기 보관할 때 target, endpoint, instance_id, session_generation, 수집 시점을 함께 기록한다.
- kernel boot/reboot/panic은 UART 증적으로 판단하고, steady-state는 SSH/journal/`dmesg`/`/sys`를 함께 본다.

## CLI fallback

MCP 기능 제약, adapter 연결 진단, 사람용 interactive console 또는 read-only live watch가 필요한 경우
CLI를 사용한다.

```bash
python3 tools/uart/integration/cli.py --target sk status
python3 tools/uart/integration/cli.py --target sk tail --lines 80
python3 tools/uart/integration/cli.py --target sk watch --backlog-lines 40
python3 tools/uart/integration/cli.py --target sk attach --backlog-lines 20
python3 tools/uart/integration/cli.py --target tmds command 'uname -a' --expect '# ' --timeout 10
```

CLI `send` 기본값은 개행 없음이며 `--newline`으로 LF를 넣는다. CLI `expect`는 기본 buffer 검색,
`--fresh`는 요청 이후 검색이다. MCP `uart_expect` 기본값은 `from="now"`이므로 구분한다.
CLI `tail`은 backlog 후 계속 구독하며 단발 조회가 아니다. `tail`/`watch` 종료는 Ctrl-C다.
`attach`는 Ctrl-] 다음 q로 종료한다.

## 통합 검증 기록

2026-11-05 초기 통합에서 로컬 fake serial/socket 테스트를 수행했다.
원격 SK/TMDS 모두 인증된 status/tail/ports 조회와 MCP stdio initialize/list/call에 성공했다.
조회 시 두 보드는 `serial_state=connected`, 최근 로그는 Linux root prompt였다.
초기 통합 검증은 읽기 전용으로 수행했다. 후속 정리에서는 두 보드 각각 CLI `attach`를
pseudo-terminal에서 실행하고 marker 출력/`uname -n` 입력, 보드 출력/root prompt 수신,
`Ctrl-]` 다음 q 종료를 확인했다. 종료 후 두 daemon의 `attach_clients=0`도 확인했다.
실제 reboot와 원격 포트/baud 변경은 실행하지 않았다.

상세 증적: [2026-11-05 폴더 정리 및 attach 검증](../bringup-logs/2026-11-05_uart-tool-cleanup-and-attach-validation.md).

이후 사용자가 제공한 새 `manuals/`, `python/` 배포본으로 교체하고 공식/repo 계층을 최종 정리했다.
이 구조의 검증 기록은 [공식 소스 재구성 및 보드 확인](../bringup-logs/2026-11-05_uart-official-source-reorganization.md)을 따른다.

배포 매뉴얼 원본은 `tools/uart/official/manuals/`, 실제 프로젝트용 인자/설정의 기준은
`tools/uart/README.md`와 repo MCP tool schema다.
