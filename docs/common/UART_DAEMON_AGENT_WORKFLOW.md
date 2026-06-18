# UART Daemon / Agent Workflow

## 목적

이 문서는 TI_Bringup 저장소에서 host 측 UART helper를 **daemon + client** 구조로 운용하는 이유와 실제 사용 절차를 정리한다.

대상 상황:

- reboot 직후 boot log를 계속 수집해야 하는 경우
- autoboot 중단, U-Boot prompt 진입, Linux login prompt 확인을 자동화해야 하는 경우
- 사람과 Agent가 같은 UART 세션을 동시에 관찰하거나 제어해야 하는 경우
- UART 출력 전체를 `logs/runtime_log`에 지속적으로 남겨야 하는 경우

## 구성 요소

`tools/uart/` 아래의 관련 helper는 daemon 중심으로 운용한다.

- `uartd.py`
  - UART port owner daemon
  - `/dev/ttyUSB*`를 계속 열고 유지한다.
  - 모든 UART 출력을 `logs/runtime_log`에 append한다.
  - local Unix domain socket과 TCP 제어 인터페이스를 제공할 수 있다.
- `uartctl.py`
  - daemon client CLI
  - `status`, `send`, `expect`, `command`, `tail`, `attach`, `watch`, `stop` 같은 제어를 수행한다.
  - 기본 transport는 target profile 기반 TCP다.
- `uart-mcp-server.py`
  - Agent가 사용하는 MCP adapter
  - UART를 직접 열지 않고 target profile이 가리키는 daemon JSON API만 호출한다.

## 언제 daemon 모델을 써야 하는가

다음 중 하나라도 해당하면 `uartd.py` + `uartctl.py`를 우선 고려한다.

- 한 프로세스가 UART를 계속 점유해야 한다.
- 사람은 계속 UART 출력을 보고 있고, 다른 Agent는 필요 시 명령을 보내야 한다.
- serial port를 여러 도구가 번갈아 다시 여는 것보다 단일 owner가 더 안전하다.
- `logs/runtime_log`를 세션 전체 증적으로 일관되게 유지해야 한다.

현재 저장소 기준 권장 모델은 daemon owner + client 제어 구조다.

## 기본 파일

daemon 기본 경로는 다음과 같다.

```text
logs/runtime_log   UART output append log
logs/uartd.sock    local Unix socket control channel (fallback)
logs/uartd.pid     daemon pid file
logs/uartd.log     daemon internal log
tools/uart/targets.json  target name -> TCP/Unix endpoint profile
```

## 기본 사용 순서

### 1. daemon 시작

```bash
./tools/uart/uartd.py start --port /dev/ttyUSB1 --baud 115200
```

의미:

- UART port를 daemon이 점유한다.
- 이후 모든 UART 출력은 `logs/runtime_log`에 append된다.
- Linux/WSL에서는 기본적으로 Unix socket과 TCP `127.0.0.1:17001`이 함께 열린다.
- 다른 프로세스는 serial port를 직접 열지 말고 `uartctl.py`로 접근한다.

### 2. 상태 확인

```bash
./tools/uart/uartctl.py status
```

기본 target은 `tools/uart/targets.json`의 `default_target`이며 현재는 `sk`다. 즉 인자를 생략하면 기본적으로 TCP `127.0.0.1:17001`로 접속한다.

다른 target 예시:

```bash
./tools/uart/uartctl.py --target custom status
```

예상 정보:

- daemon pid
- UART port
- baudrate
- socket path
- runtime log path
- 연결된 client 수
- 현재 daemon 수신 offset
- backlog 시작 offset
- 현재 메모리 buffer 길이

### 3. 출력 관찰

방법 A: daemon client로 보기

```bash
./tools/uart/uartctl.py tail
```

방법 B: raw log 파일 직접 보기

```bash
tail -f logs/runtime_log
```

사람이 계속 UART 출력을 확인하려면 보통 방법 B가 가장 단순하다.

방법 C: read-only raw UART 콘솔처럼 보기

```bash
./tools/uart/uartctl.py watch
```

`watch`는 read-only live console이다. backlog를 같이 보려면 `--backlog-lines`를 사용한다.

### 4. 입력 전송

줄바꿈 없이 raw text 전송:

```bash
./tools/uart/uartctl.py send "boot"
```

줄바꿈 포함 전송:

```bash
./tools/uart/uartctl.py send "printenv bootcmd" --newline
./tools/uart/uartctl.py send "" --newline
```

마지막 예시는 autoboot 중단용 Enter 입력에 사용할 수 있다.

직접 interactive console처럼 붙으려면:

```bash
./tools/uart/uartctl.py attach
```

기본 detach sequence는 `Ctrl-]` 다음 `q`다.

### 4.1 프롬프트 동기화 command 전송

현재 저장소의 권장 제어 방식은 `send`와 `expect`를 따로 분리하는 것보다,
하나의 command 요청에서 전송과 기대 문자열 대기를 함께 묶는 것이다.

```bash
./tools/uart/uartctl.py command "usb start" --expect "=> " --timeout 20
./tools/uart/uartctl.py command "printenv bootcmd" --expect "=> " --timeout 5
./tools/uart/uartctl.py command "root" --expect "root@am64xx-evm:~#" --timeout 10
```

이 방식의 목적:

- 예전 backlog 안에 남아 있던 `=> ` 또는 `login:`을 새 프롬프트로 오인하지 않기
- command 전송 직후의 새 UART 출력만 기준으로 다음 prompt를 기다리기
- 성공 시 실제 UART output text와 match offset을 함께 받아 후속 판단에 쓰기

### 5. 문자열 대기

```bash
./tools/uart/uartctl.py expect "Hit any key to stop autoboot" --timeout 5
./tools/uart/uartctl.py expect "=> " --timeout 3
./tools/uart/uartctl.py expect "login:" --timeout 60
```

`expect`는 현재 daemon이 보유 중인 UART backlog와 이후 새로 들어오는 출력 모두를 기준으로 매치한다.
현재 구현에서는 match 성공 시 `output`, timeout 시 `tail`과 `output_since_start`도 함께 반환하므로,
상위 Agent가 timeout 이후 현재 상태를 다시 해석하기 쉽다.

새 출력만 기준으로 대기하고 싶으면 `--fresh`를 사용한다.

```bash
./tools/uart/uartctl.py expect "login:" --timeout 10 --fresh
./tools/uart/uartctl.py expect "=> " --timeout 5 --fresh
```

특정 daemon offset 이후만 보고 싶으면 `--from-offset`를 사용한다.

```bash
./tools/uart/uartctl.py expect "=> " --from-offset 1200 --timeout 5
```

## backlog-aware expect 와 fresh expect 의 차이

`uartd.py`는 UART 전체 backlog를 메모리 buffer에 유지한다. 그래서 단순 `expect`는 과거에 이미 출력된
문자열도 바로 매치할 수 있다.

```text
expect
  - daemon backlog + 새 출력 모두 검색
  - 로그 관찰/상태 확인에는 유용

expect --fresh
  - 요청 시점 이후 새 출력만 검색
  - U-Boot prompt 동기화, login prompt 동기화에 권장

command --expect
  - daemon 내부에서 send + expect 를 하나의 transaction 으로 처리
  - 제어용 자동화에서는 가장 권장
```

### 6. daemon 종료

```bash
./tools/uart/uartctl.py stop
```

## 예시 workflow

### reboot 감시 후 U-Boot 진입

terminal A:

```bash
./tools/uart/uartd.py start --port /dev/ttyUSB1 --baud 115200
./tools/uart/uartctl.py attach
```

terminal B:

```bash
./tools/uart/uartctl.py expect "Hit any key to stop autoboot" --timeout 5 --fresh
./tools/uart/uartctl.py send "" --newline
./tools/uart/uartctl.py expect "=> " --timeout 3 --fresh
./tools/uart/uartctl.py command "printenv bootcmd" --expect "=> " --timeout 3
```

이 구조에서는 사람은 terminal A에서 raw UART를 계속 보고, Agent 또는 사용자 명령은 terminal B에서 수행할 수 있다.

## Agent 사용 원칙

- 상위 Agent는 가능하면 serial port를 직접 다시 열지 않는다.
- 이미 `uartd.py`가 실행 중이면 `uartctl.py`를 통해 접근한다.
- `logs/runtime_log`는 UART 1차 증적이므로, 자동화 중에도 다른 terminal에서 확인 가능해야 한다.
- 장시간 세션 중 예상 밖 동작이 보이면 `runtime_log`, `uartd.log`, `status` 정보를 함께 본다.
- 제어 자동화에서는 backlog-aware `expect`보다 `command --expect` 또는 `expect --fresh`를 우선 사용한다.
- 현재 프롬프트가 불확실하면 먼저 empty newline을 보내고(`send "" --newline`), 그 뒤 원하는 프롬프트를 fresh mode로 확인한다.
- 커스텀 보드 target은 원격 host에서 daemon이 실행될 수 있으므로, 원격 host의 `logs/runtime_log` 파일 자체를 local filesystem 증적으로 직접 참조할 수 있다고 가정하지 않는다.

## 운영 주의사항

- UART port는 한 번에 하나의 owner만 여는 것이 안전하다. daemon 모델에서는 `uartd.py`만 owner다.
- daemon 실행 중 다른 terminal에서 `picocom`, `screen`, `minicom`, 별도 Python script 등으로 같은 port를 다시 열면 충돌할 수 있다.
- `runtime_log`는 append되므로, 새 세션 구분이 필요하면 시작 전에 백업하거나 rotate 정책을 따로 둔다.
- `uartctl.py tail`은 편의용 stream이고, 원본 증적 확인은 `logs/runtime_log` 기준으로 판단한다.
- `uartctl attach`는 terminal raw mode를 사용하므로 비정상 종료 시 `reset` 또는 `stty sane`가 필요할 수 있다.

## 권장 모델

현재 저장소의 기본 UART 운용 모델은 `uartd.py` + `uartctl.py`다.

- `uartd.py`
  - UART owner
  - `logs/runtime_log` 증적 유지
- `uartctl.py`
  - 사용자/Agent 제어 인터페이스
  - `status`, `send`, `expect`, `tail`, `stop`

즉 **계속 붙어 있는 UART owner와 외부 제어 인터페이스**가 기본이고, 사람과 Agent는 같은 daemon 세션을 공유하는 방향으로 운용한다.

## MCP adapter

Agent는 `tools/uart/uart-mcp-server.py`를 통해 UART daemon에 접근할 수 있다.

기본 운용은 generic `uart` MCP 하나를 사용하고, tool argument의 `target`으로 `sk` 또는 `custom`을 선택하는 방식이다.

기본 구조:

```text
opencode Agent
  -> MCP stdio
  -> uart-mcp-server.py
  -> target profile (`sk`, `custom`)
  -> tcp://127.0.0.1:17001 or target-specific endpoint
  -> uartd.py
  -> /dev/ttyUSBx or remote host serial port
```

초기 MCP tool은 다음 5개를 기준으로 한다.

- `uart_status`
- `uart_tail`
- `uart_sendline`
- `uart_expect`
- `uart_command`

중요 원칙:

- MCP adapter는 UART 포트를 직접 열지 않는다.
- UART owner는 항상 `uartd.py` 하나다.
- 사람이 `attach` 중이어도 MCP write는 차단하지 않는다.
- MCP command 중에도 attach 입력은 차단하지 않는다.
- target 선택은 별도 MCP alias가 아니라 tool argument의 `target`으로 수행한다.
