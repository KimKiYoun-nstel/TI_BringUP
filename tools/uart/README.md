# UART TCP 사용 가이드

## 목적

이 문서는 WSL host에서 `uartd.py`를 실행하고, `uartctl.py`가 TCP로 SK-AM64B UART 세션에 접속하는 기본 절차를 간단히 정리한다.

현재 `tools/uart/` 구조는 다음과 같다.

- `uartd.py`: UART port owner daemon
- `uartctl.py`: daemon client CLI
- `uart-mcp-server.py`: Agent용 MCP adapter
- `targets.json`: named target과 TCP endpoint 설정

기본 모델은 다음과 같다.

```text
SK-AM64B debug UART (/dev/ttyUSB1)
  -> uartd.py 가 포트를 계속 점유
  -> TCP 127.0.0.1:17001 로 제어 API 제공
  -> uartctl.py 가 TCP client로 접속
  -> 모든 UART 출력은 logs/runtime_log 에 append
```

## 사전 조건

- SK-AM64B debug UART가 WSL에서 `/dev/ttyUSB*`로 보여야 한다.
- Python 3가 있어야 한다.
- `pyserial`이 설치되어 있어야 한다.

```bash
python3 -m pip install pyserial
```

포트 확인 예:

```bash
ls -l /dev/ttyUSB*
```

## WSL host에서 uartd 시작

가장 단순한 시작 예시는 다음과 같다.

```bash
cd ~/ti/TI_Bringup
python3 tools/uart/uartd.py start --port /dev/ttyUSB1 --baud 115200
```

이 명령의 의미:

- UART 포트 owner를 `uartd.py` 하나로 고정한다.
- WSL/Linux에서는 기본적으로 Unix socket과 TCP를 함께 연다.
- 기본 TCP endpoint는 `127.0.0.1:17001`이다.
- UART 출력은 `logs/runtime_log`에 계속 누적된다.
- daemon 내부 로그는 `logs/uartd.log`에 남는다.

TCP만 명시적으로 열고 싶으면 다음처럼 실행할 수 있다.

```bash
python3 tools/uart/uartd.py start \
  --port /dev/ttyUSB1 \
  --baud 115200 \
  --tcp-host 127.0.0.1 \
  --tcp-port 17001 \
  --no-unix-socket
```

WSL 밖의 다른 client가 붙어야 하면 bind host를 `0.0.0.0`으로 바꿔서 노출할 수 있다.

```bash
python3 tools/uart/uartd.py start \
  --port /dev/ttyUSB1 \
  --baud 115200 \
  --tcp-host 0.0.0.0 \
  --tcp-port 17001
```

외부 노출 시에는 접근 가능한 host/IP와 방화벽 정책을 함께 확인한다.

## 현재 기본 target 설정

`tools/uart/targets.json`의 기본값은 다음과 같다.

```json
{
  "default_target": "sk",
  "targets": {
    "sk": {
      "transport": "tcp",
      "tcp": "127.0.0.1:17001"
    }
  }
}
```

즉 `uartctl.py`에서 target을 생략하면 기본적으로 `sk -> 127.0.0.1:17001`로 접속한다.

## uartctl 사용법

### 상태 확인

```bash
python3 tools/uart/uartctl.py status
python3 tools/uart/uartctl.py --target sk status
python3 tools/uart/uartctl.py --tcp 127.0.0.1:17001 status
```

확인 포인트:

- daemon pid
- UART port
- baudrate
- TCP endpoint
- `logs/runtime_log` 경로
- client 수
- 현재 UART buffer offset

### 최근 UART 출력 보기

```bash
python3 tools/uart/uartctl.py tail
python3 tools/uart/uartctl.py watch
tail -f logs/runtime_log
```

- `tail`: daemon backlog와 이후 새 출력을 계속 출력
- `watch`: read-only live console
- `logs/runtime_log`: UART 1차 증적 로그

### 입력 전송

```bash
python3 tools/uart/uartctl.py send "" --newline
python3 tools/uart/uartctl.py send "printenv bootcmd" --newline
```

- 첫 번째 예시는 autoboot 중단용 Enter 입력에 쓸 수 있다.
- 두 번째 예시는 U-Boot prompt에 명령 한 줄을 보낸다.

### 문자열 대기

```bash
python3 tools/uart/uartctl.py expect "Hit any key to stop autoboot" --timeout 5 --fresh
python3 tools/uart/uartctl.py expect "=> " --timeout 3 --fresh
python3 tools/uart/uartctl.py expect "login:" --timeout 60 --fresh
```

- `--fresh`는 요청 이후의 새 출력만 기준으로 찾는다.
- prompt 동기화에는 backlog 검색보다 `--fresh`가 안전하다.

### send + expect를 한 번에 수행

제어 자동화에서는 `command`가 가장 편하다.

```bash
python3 tools/uart/uartctl.py command "usb start" --expect "=> " --timeout 20
python3 tools/uart/uartctl.py command "printenv bootcmd" --expect "=> " --timeout 5
```

이 방식은 명령 전송과 다음 prompt 대기를 같은 transaction으로 처리한다.

### interactive attach

```bash
python3 tools/uart/uartctl.py attach
```

- detach: `Ctrl-]` 다음 `q`
- 사람이 raw console을 직접 보면서 입력할 때 사용한다.

### daemon 종료

```bash
python3 tools/uart/uartctl.py stop
```

## 가장 자주 쓰는 흐름

### 1. WSL에서 daemon 시작

```bash
python3 tools/uart/uartd.py start --port /dev/ttyUSB1 --baud 115200
```

### 2. 다른 terminal에서 상태 확인

```bash
python3 tools/uart/uartctl.py status
```

### 3. UART 로그 보기

```bash
tail -f logs/runtime_log
```

### 4. U-Boot 진입 예시

```bash
python3 tools/uart/uartctl.py expect "Hit any key to stop autoboot" --timeout 5 --fresh
python3 tools/uart/uartctl.py send "" --newline
python3 tools/uart/uartctl.py expect "=> " --timeout 3 --fresh
```

### 5. U-Boot 명령 실행 예시

```bash
python3 tools/uart/uartctl.py command "printenv bootcmd" --expect "=> " --timeout 5
```

## 로그와 문제 확인 지점

- UART 원문 증적: `logs/runtime_log`
- daemon 내부 로그: `logs/uartd.log`
- daemon pid: `logs/uartd.pid`

문제가 있으면 아래 순서로 본다.

1. `python3 tools/uart/uartctl.py status`
2. `tail -f logs/uartd.log`
3. `tail -f logs/runtime_log`

## 주의사항

- serial port는 `uartd.py`만 직접 열어야 한다.
- `picocom`, `screen`, `minicom` 같은 다른 tool이 같은 포트를 동시에 열면 충돌할 수 있다.
- prompt 기준 자동화는 `expect --fresh` 또는 `command --expect`를 우선 사용한다.
- 원격/외부 TCP 노출이 필요 없으면 `127.0.0.1` bind를 유지하는 편이 안전하다.

## 관련 문서

- `docs/common/UART_DAEMON_AGENT_WORKFLOW.md`
- `docs/boards/SK-AM64B/uart-console-windows.md`
