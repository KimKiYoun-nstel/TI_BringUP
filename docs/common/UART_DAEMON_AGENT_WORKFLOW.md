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
  - local Unix domain socket으로 제어 인터페이스를 제공한다.
- `uartctl.py`
  - daemon client CLI
  - `status`, `send`, `expect`, `tail`, `stop` 같은 제어를 수행한다.

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
logs/uartd.sock    local Unix socket control channel
logs/uartd.pid     daemon pid file
logs/uartd.log     daemon internal log
```

## 기본 사용 순서

### 1. daemon 시작

```bash
./tools/uart/uartd.py start --port /dev/ttyUSB1 --baud 115200
```

의미:

- UART port를 daemon이 점유한다.
- 이후 모든 UART 출력은 `logs/runtime_log`에 append된다.
- 다른 프로세스는 serial port를 직접 열지 말고 `uartctl.py`로 접근한다.

### 2. 상태 확인

```bash
./tools/uart/uartctl.py status
```

예상 정보:

- daemon pid
- UART port
- baudrate
- socket path
- runtime log path
- 연결된 client 수

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

### 5. 문자열 대기

```bash
./tools/uart/uartctl.py expect "Hit any key to stop autoboot" --timeout 5
./tools/uart/uartctl.py expect "=> " --timeout 3
./tools/uart/uartctl.py expect "login:" --timeout 60
```

`expect`는 현재 daemon이 보유 중인 UART backlog와 이후 새로 들어오는 출력 모두를 기준으로 매치한다.

### 6. daemon 종료

```bash
./tools/uart/uartctl.py stop
```

## 예시 workflow

### reboot 감시 후 U-Boot 진입

terminal A:

```bash
./tools/uart/uartd.py start --port /dev/ttyUSB1 --baud 115200
tail -f logs/runtime_log
```

terminal B:

```bash
./tools/uart/uartctl.py expect "Hit any key to stop autoboot" --timeout 5
./tools/uart/uartctl.py send "" --newline
./tools/uart/uartctl.py expect "=> " --timeout 3
./tools/uart/uartctl.py send "printenv bootcmd" --newline
./tools/uart/uartctl.py expect "=> " --timeout 3
```

이 구조에서는 사람은 terminal A에서 raw UART를 계속 보고, Agent 또는 사용자 명령은 terminal B에서 수행할 수 있다.

## Agent 사용 원칙

- 상위 Agent는 가능하면 serial port를 직접 다시 열지 않는다.
- 이미 `uartd.py`가 실행 중이면 `uartctl.py`를 통해 접근한다.
- `logs/runtime_log`는 UART 1차 증적이므로, 자동화 중에도 다른 terminal에서 확인 가능해야 한다.
- 장시간 세션 중 예상 밖 동작이 보이면 `runtime_log`, `uartd.log`, `status` 정보를 함께 본다.

## 운영 주의사항

- UART port는 한 번에 하나의 owner만 여는 것이 안전하다. daemon 모델에서는 `uartd.py`만 owner다.
- daemon 실행 중 다른 terminal에서 `picocom`, `screen`, `minicom`, 별도 Python script 등으로 같은 port를 다시 열면 충돌할 수 있다.
- `runtime_log`는 append되므로, 새 세션 구분이 필요하면 시작 전에 백업하거나 rotate 정책을 따로 둔다.
- `uartctl.py tail`은 편의용 stream이고, 원본 증적 확인은 `logs/runtime_log` 기준으로 판단한다.

## 권장 모델

현재 저장소의 기본 UART 운용 모델은 `uartd.py` + `uartctl.py`다.

- `uartd.py`
  - UART owner
  - `logs/runtime_log` 증적 유지
- `uartctl.py`
  - 사용자/Agent 제어 인터페이스
  - `status`, `send`, `expect`, `tail`, `stop`

즉 **계속 붙어 있는 UART owner와 외부 제어 인터페이스**가 기본이고, 사람과 Agent는 같은 daemon 세션을 공유하는 방향으로 운용한다.
