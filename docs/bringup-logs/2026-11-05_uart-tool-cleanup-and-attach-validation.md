# UART 도구 정리 및 실보드 attach 입출력 검증

> 이 문서는 초기 정리 당시 경로·검증 이력이다. 최종 구조와 최신 확인은
> [공식 소스 재구성 및 보드 확인](2026-11-05_uart-official-source-reorganization.md)을 따른다.

## 목적과 정리 내용

이전 WSL 작업 환경에서 사용하던 serial 직접 접근 도구와 중복 wrapper를 정리하고,
원격 daemon을 통한 실제 CLI attach 입출력을 검증했다.

- 삭제: `tools/uart/uart_agent.py`, `uart_expect.py`, `uart-agent-example.json`.
- MCP 진입점 통합: `uart-mcp-server.py` launcher를 제거하고 `uart_mcp_server.py`를
  `mcp_server.py`로 변경. MCP 설정·문서·테스트 참조를 함께 갱신했다.
- 공통 설정 코드: `uart_endpoint.py` → `lib/endpoint.py`.
- API wrapper 제거: `uart_api.py` 대신 CLI/MCP가 `upstream/uart_api.py`를 직접 import.
- 배포 ZIP 3개: `archives/`로 이동. ZIP 자체는 Git 제외 상태로 로컬 보관한다.
- 배포 원본 `upstream/` 및 보드별 `.secrets/` 인증 파일은 유지한다.

실행 진입점은 루트의 `uartctl.py`, `uartd.py`, `mcp_server.py` 세 개다.
전체 GUI/EXE 빌드 자료까지 필요한 경우 `archives/`의 원본 ZIP을 사용한다.
현재 실행에 필요한 배포 소스·매뉴얼·테스트는 `upstream/`에 반입되어 있다.

## 실보드 검증 방법

검증 단계는 Linux root shell이다. 먼저 각 target의 MCP status/tail에서 연결과 root prompt를
확인한 후, Python 표준 라이브러리 `pty`로 실제 CLI의 interactive attach를 실행했다.
UART 물리 포트는 원격 daemon만 소유하며 현 Ubuntu에서는 TCP client만 실행했다.

```bash
python3 -B tools/uart/uartctl.py --target sk attach --backlog-lines 0
python3 -B tools/uart/uartctl.py --target tmds attach --backlog-lines 0
```

각 terminal에서 다음 명령을 전송했다.

```sh
# SK
printf 'UART_ATTACH_%s_OK\n' SK; uname -n
# TMDS
printf 'UART_ATTACH_%s_OK\n' TMDS; uname -n
```

marker 전체 문자열은 전송 명령에 연속해서 포함되지 않으므로 단순 command echo와 구분된다.
명령을 처리한 보드 출력에서 marker와 hostname, root prompt를 확인했다.
검증 후 `Ctrl-]` 다음 q를 전송해 attach process가 exit code 0으로 종료되는지 확인했다.

## 결과

| target | endpoint | 연결 | instance_id | session_generation |
|---|---|---|---|---|
| `sk` | `192.168.0.33:17001` | COM10 / 115200 | `am64_sk_board` | 17 |
| `tmds` | `192.168.0.33:17002` | COM7 / 115200 | `tmds_board` | 9 |

SK 수신:

```text
UART_ATTACH_SK_OK
am64xx-evm
root@am64xx-evm:~#
```

TMDS 수신:

```text
UART_ATTACH_TMDS_OK
am64xx-evm
root@am64xx-evm:~#
```

두 보드 모두 attach TX/RX 및 detach 성공.
종료 후 MCP status에서 두 target 모두 `serial_state=connected`, `attach_clients=0`을 확인했다.
검증 전후 session_generation도 동일하다. SK offset은 14487 → 14580,
TMDS offset은 1131 → 1228로 증가했다.

## 로컬 검증

- `python3 -B -m unittest discover -s tests/tools/uart -v`: 10개 통과.
- 테스트용 venv에서 `PYTHONPATH=tools/uart/upstream python -m pytest -q tools/uart/upstream/tests`:
  8개 통과.
- `opencode mcp list`: `/usr/bin/python3 ./tools/uart/mcp_server.py` 연결 성공.
- `git diff --check`: 통과.

초기 업데이트의 읽기 전용 검증에 더해 이번 기록으로 실보드 CLI attach 입출력을 확인했다.
reboot/포트 전환/baud 변경은 수행하지 않았다. 포트 전환·복구 시나리오는 로컬 fake serial 테스트로
검증한 범위이며, 실제 장비의 USB 재연결 및 장시간 운용은 해당 작업에서 확인한다.

## 최종 관리 경계 확정 및 재검증

사용자 합의에 따라 MCP server는 repo마다 독립 구성하고, 공식 MCP는 UART API 호출의
참고 구현/가이드로 관리한다. 공식 UART 프로젝트의 daemon/CLI/API/문서와 repo adapter의
소유권을 구분했다.

- `upstream/`: 공식 코드·매뉴얼·테스트를 원본 그대로 Git에서 관리한다.
  참고용 공식 `uart_mcp.py`도 반입했으며 repo MCP의 실행 의존성에는 포함하지 않는다.
- `mcp_server.py`: 일반 TCP 요청을 공식 `uart_api.request()`에 위임한다.
  공식 API가 TCP 전용이므로 로컬 Unix socket 연결 adapter는 유지한다.
- `upstream-release.json`: 버전 `0.1.0-dev`, 반입 범위와 원본 manifest 해시를 기록한다.
- `verify_upstream.py`: 공식 파일 23개와 manifest 무결성 검사를 수행한다.
- `UPGRADING.md`: 외부 새 배포본 반입, adapter 연동, 회귀 검증 절차를 기록했다.

앞선 단계의 ZIP 보관 안내는 source/docs 직접 관리로 대체했다. 로컬에 남아 있는 ZIP은
Git 제외 입력 자료이며 clone·실행·갱신 기준이 아니다.

최종 API 위임 변경 후 재검증 결과:

- 공식 파일 23개 SHA-256 일치.
- repo unittest 10개, 공식 pytest 8개 통과.
- 새 MCP client 경로로 두 target 인증/status 확인:
  SK `am64_sk_board`, COM10/115200, generation 17;
  TMDS `tmds_board`, COM7/115200, generation 9. 모두 `serial_state=connected`.
- `opencode mcp list` 연결 및 `git diff --check` 통과.

이번 최종 단계는 TCP 요청 경로와 관리 문서 변경이며, CLI attach 코드는 변경하지 않았다.
실보드 attach 결과는 앞 절의 검증을 적용한다.
