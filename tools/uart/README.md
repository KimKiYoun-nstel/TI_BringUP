# TI_Bringup UART 도구 모음

공식 UART Tool 배포 코드와 TI_Bringup 전용 연동 코드를 함께 관리한다.
현재 공식 원천은 사용자가 제공한 `manuals/`, `python/` 배포본이며,
두 폴더의 `VERSION`은 `0.1.0-dev`다.

## 디렉터리와 책임

```text
tools/uart/
  README.md
  UPGRADING.md                 공식 배포본 갱신 절차
  official/                    공식 원천, repo 맞춤 수정은 하지 않음
    manuals/                   공식 사용자·Python·API·MCP 매뉴얼
    python/                    공식 Python 소스와 VERSION
      uart_api.py              TCP JSON 요청·응답 API
      uartctl.py               CLI, attach/watch 구현
      uartd.py                 UART 소유 daemon
      uart_runtime.py          daemon I/O worker·로그 구현
      uartgui.py               공식 GUI
      uart_mcp.py              공식 MCP 예제
  integration/                 이 repo에서 수정·확장하는 연동 코드
    distribution.py            공식 standalone Python 모듈 로딩
    endpoint.py                target·endpoint·토큰 해석
    cli.py                     공식 CLI에 --target/--targets-file 추가
    mcp_server.py              repo 독립 MCP stdio 서버
  config/
    targets.json               보드별 endpoint·토큰 파일 경로
  .secrets/                    로컬 인증 파일, Git 제외
```

공식 코드의 버그 수정은 공식 프로젝트에서 배포 후 반입한다.
이 repo의 target 정책, MCP 도구와 bring-up 흐름은 `integration/`에서 수정한다.
공식 `uart_mcp.py`는 참고 예제이며 실제 OpenCode MCP 실행 대상은
`integration/mcp_server.py`다. 공식 배포본은 코드·문서 자체를 Git으로 관리하며
별도 파일 해시, manifest, 해시 검사기는 사용하지 않는다.

```text
OpenCode ── stdio MCP ── integration/mcp_server.py
                              │ target·토큰·bring-up 도구
                         official/python/uart_api.py
                              │ TCP JSON API
                    원격 uartd ── Serial ── 보드
```

MCP 서버는 로컬 stdio 프로세스이며 별도 TCP listener를 열지 않는다.
TCP 통신은 공식 `uart_api.request()`를 사용한다. Unix socket 연동에만
공식 API의 JSON reader를 재사용하는 repo 호환 경로가 있다.
`cli.py`는 공식 CLI의 attach/watch/command 구현을 재사용한다.

## 보드와 인증

| target | endpoint | 보드 |
|---|---|---|
| `sk` (기본) | `192.168.0.33:17001` | SK-AM64B |
| `tmds` | `192.168.0.33:17002` | TMDS64EVM |

`config/targets.json`의 `token_file`은 해당 JSON 폴더 기준 상대 경로다.
현재 각각 `../.secrets/sk.token`, `../.secrets/tmds.token`을 사용한다.
토큰은 Git에 추가하지 않는다. 파일 권한은 `600`, `.secrets/`는 `700`을 사용한다.

토큰 우선순위:

1. `--token-file`
2. `UARTD_TOKEN_FILE`
3. `UARTD_TOKEN`
4. target profile의 `token_file`

`--tcp` 또는 `--socket`은 target endpoint보다 우선한다. endpoint를 직접 지정하면
target 토큰을 자동 선택하지 않으므로 `--token-file` 또는 환경 변수를 지정한다.
CLI/API 및 repo MCP는 Python 표준 라이브러리만으로 실행된다.
공식 daemon/GUI/공식 MCP를 직접 실행하는 경우의 의존성은
[공식 Python README](official/python/README.md)를 따른다.

## CLI 사용

저장소 루트에서 실행한다. 이 장비에서는 원격 daemon에 접속한다.

```bash
python3 tools/uart/integration/cli.py --target sk status
python3 tools/uart/integration/cli.py --target tmds status
python3 tools/uart/integration/cli.py --target sk ports
python3 tools/uart/integration/cli.py --target sk tail --lines 80
python3 tools/uart/integration/cli.py --target tmds watch --backlog-lines 40
python3 tools/uart/integration/cli.py --target sk attach --backlog-lines 20
python3 tools/uart/integration/cli.py --target sk command 'uname -n' --expect '# ' --timeout 10
python3 tools/uart/integration/cli.py --target sk send 'root' --newline
python3 tools/uart/integration/cli.py --target sk expect 'login:' --timeout 10 --fresh
```

CLI `tail`은 backlog 출력 후 JSON 이벤트를 계속 구독하며 `watch`는 RO raw 스트림이다.
둘 다 지속 감시이므로 종료는 `Ctrl-C`다. 단발 조회는 MCP `uart_tail`을 사용한다.
`attach`는 RX/TX이며 종료는 `Ctrl-]` 다음 `q`다.
`--connect-timeout`, `--response-timeout`은 subcommand 앞에 지정하며,
후자는 공식 CLI의 응답 timeout 옵션으로 그대로 전달한다.
포트 변경·연결 해제·baud 변경은 공유 사용자에게 영향을 주므로 대상 확인 후 수행한다.

```bash
python3 tools/uart/integration/cli.py --target sk port COM10 --baud 115200
python3 tools/uart/integration/cli.py --target sk baud 115200
python3 tools/uart/integration/cli.py --target sk disconnect
```

## MCP 사용

`opencode.jsonc`의 `mcp.uart`는
`/usr/bin/python3 ./tools/uart/integration/mcp_server.py`를 실행한다.
설정 변경 후에는 OpenCode를 완전히 종료하고 다시 시작한다.

도구는 `uart_status`, `uart_tail`, `uart_list_ports`, `uart_set_port`,
`uart_disconnect`, `uart_baud`, `uart_send`, `uart_sendline`, `uart_expect`,
`uart_command`, `uart_reboot_to_uboot`다. 호출마다 `target`을 지정할 수 있다.
일반 명령은 `uart_command`의 `line`을 사용한다. 공식 MCP 예제의 `text`와 구분한다.

```json
{"target":"sk"}
{"target":"tmds","line":"uname -n","expect":"# ","timeout":10}
```

첫 예시는 `uart_status`, 둘째는 `uart_command` 인자다.
먼저 status와 tail로 보드 상태를 확인한다. timeout 이후 명령을 바로 재전송하지 말고
tail을 확인한다. 공식 신규 daemon은 command에 기본 exclusive lease를 사용한다.
공유 RW attach와 command를 동시에 시작하지 말고 사용이 끝난 attach를 종료한다.
원격 daemon의 실제 버전과 기능은 별도로 확인한다. 로컬 배포본 교체는 원격 서버를 갱신하지 않는다.

## 로그·검증·갱신

UART 증적은 선택한 daemon의 `status.runtime_log`와 같은 target의 `tail`이 기준이다.
원격 Windows 로그 경로를 로컬 경로로 취급하지 않는다. 로컬 `logs/runtime_log`는
대상과 수집 시점이 맞는 복사본/링크일 때만 사용한다.

```bash
python3 -B -m unittest discover -s tests/tools/uart -v
opencode mcp list
```

repo 테스트는 새 공식 daemon을 fake serial로 실행하여 CLI/MCP 연동, 인증,
명령·timeout·attach 스트림·포트 변경을 확인한다. 실제 보드는 별도 status/tail/명령으로 확인한다.

- [공식 배포본 갱신](UPGRADING.md)
- [공식 매뉴얼](official/manuals/README.md)
- [Agent UART 워크플로](../../docs/common/UART_DAEMON_AGENT_WORKFLOW.md)
