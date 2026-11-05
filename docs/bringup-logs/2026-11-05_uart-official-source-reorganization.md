# 공식 UART 원천 재구성 및 두 보드 연결 확인

## 반입 기준과 구조

사용자가 `tools/uart/upstream/` 아래 제공한 새 `manuals/`, `python/`을 최신 공식
배포본으로 채택했다. 두 VERSION은 모두 `0.1.0-dev`다.
이전 배포본과 버전 문자열이 같더라도 새 폴더 내용이 이번 반입 기준이다.

- 공식 원천: `tools/uart/official/{manuals,python}/`로 이동.
- repo 전용: `tools/uart/integration/{distribution,endpoint,cli,mcp_server}.py`.
- 보드 설정: `tools/uart/config/targets.json`.
- 인증 파일: 기존 `tools/uart/.secrets/` 유지, Git 제외.
- 이전 공식 코드·문서·테스트 사본과 root wrapper, `lib/`, `upstream/` 제거.
- `MANIFEST.sha256.json`, `upstream-release.json`, `verify_upstream.py` 제거.
  공식 코드의 별도 파일 해시 관리는 하지 않는다.
- 이전 ignored ZIP 3개는 `/tmp/opencode/uart-superseded-archives-20261105/`로 이동하여
  운영 도구 폴더에서 제외했다. 현재 사용·갱신 기준은 실제 코드·문서다.

공식 파일은 repo용으로 수정하지 않고 재사용한다. `distribution.py`는 공식 standalone
모듈의 import 경로만 연결한다. CLI wrapper는 target·토큰 해석과 `--response-timeout`
전달을 담당한다. MCP는 공식 TCP API를 사용하며 repo의 11개 도구를 독립 제공한다.
공식 `uart_mcp.py`는 예제로 보관하며 실행 대상으로 등록하지 않는다.

새 daemon의 `uart_runtime.py` 의존성을 함께 반입했고, 기본 command exclusive lease에 맞게
테스트와 작업 문서를 갱신했다. MCP 소켓 응답 timeout에는 공식 CLI와 같이 서버 대기 시간
외에 6초를 추가하여 UART worker의 송신 응답 여유를 둔다.

## 로컬 검증

```bash
python3 -B -m unittest discover -s tests/tools/uart -v
opencode mcp list
git diff --check
```

- repo 연동 테스트 10개 통과: 새 공식 daemon을 fake serial로 실행하여 인증·target routing,
  CLI subprocess, MCP stdio, command/timeout, raw attach/watch, 포트 변경·실패 보존 확인.
- 새 경로 `/usr/bin/python3 ./tools/uart/integration/mcp_server.py` 연결 성공.
- 별도로 새 MCP subprocess에 initialize → tools/list → tools/call 수행, 11개 도구 확인.
- 새 공식 배포본에는 테스트 묶음이 없으므로 이전 공식 테스트 사본은 유지하지 않았다.

## 실제 보드 증적

두 보드 모두 CLI wrapper의 인증된 status와 새 MCP subprocess의 status/tail을 먼저 확인했다.
두 target의 tail에서 Linux root prompt를 확인한 뒤 새 MCP `uart_command`로 실행했다.

| target | endpoint | UART | instance_id | generation | 결과 |
|---|---|---|---|---|---|
| sk | 192.168.0.33:17001 | COM10 / 115200 | am64_sk_board | 1 | connected, 명령 응답 성공 |
| tmds | 192.168.0.33:17002 | COM7 / 115200 | tmds_board | 1 | connected, 명령 응답 성공 |

실행 명령:

```sh
# sk
printf 'UART_FINAL_%s_OK\n' SK; uname -n
# tmds
printf 'UART_FINAL_%s_OK\n' TMDS; uname -n
```

각각 `UART_FINAL_SK_OK`, `UART_FINAL_TMDS_OK`, hostname `am64xx-evm`,
`root@am64xx-evm:~# `를 수신했다. marker 완성 문자열은 송신 명령에 연속해서 들어 있지
않으므로 입력 echo만으로 성공을 판단한 것이 아니다. 두 command 모두 `ok=true`,
`shared_write=false`, 약 51ms였으며 offset은 SK `63 → 154`, TMDS `21 → 116`이었다.
두 보드의 RW/RO attach 수는 0이었고 TMDS에는 기존 JSON monitor가 있었다.
이전 검증 기록의 generation과 다르므로 이번 값을 현재 세션 기준으로 기록한다.

증적 원본은 원격 daemon의 다음 로그다. 로컬 자동 동기화는 없다.

```text
D:\WORKS\uartTool_GUI_Project_v0.1.0-dev\uartTool_GUI_Project\dist\logs\runtime_log-am64_sk_board
D:\WORKS\uartTool_GUI_Project_v0.1.0-dev\uartTool_GUI_Project\dist\logs\runtime_log-tmds_board
```

## 검증 중 확인한 동작과 적용 사항

- 현재 실행 중인 OpenCode MCP는 이전 target 설정 경로를 이미 로드한 상태여서
  root의 `targets.json` 이동 후 localhost fallback/unknown target 오류가 발생했다.
  새 경로의 CLI와 MCP subprocess에서는 두 보드 모두 정상 동작했다.
  **OpenCode를 완전히 종료하고 재시작해야 기존 세션의 UART 도구도 새 구조를 사용한다.**
- 공식 CLI `tail`은 backlog 후 계속 이벤트를 구독한다. 최초 확인 명령은 정상 출력을
  수신한 뒤 도구의 실행 시간 제한으로 종료되었다. 단발 조회는 MCP `uart_tail`로
  다시 확인했다. CLI `tail`/`watch`는 사람이 Ctrl-C로 종료하도록 문서를 보완했다.
- 이번 최종 연결 확인은 status/tail과 간단한 shell 명령 범위다.
  이전 실제 attach 검증은 [초기 정리 기록](2026-11-05_uart-tool-cleanup-and-attach-validation.md)에 있다.

## 사용·갱신 기준

- [UART 도구 안내](../../tools/uart/README.md)
- [공식 배포본 갱신](../../tools/uart/UPGRADING.md)
- [Agent 워크플로](../common/UART_DAEMON_AGENT_WORKFLOW.md)

향후 공식 원천 갱신은 `official/python/`, `official/manuals/`를 함께 교체하고
repo 연동 테스트 및 보드 송수신을 확인한다. repo 맞춤 변경은 `integration/`에 반영한다.
