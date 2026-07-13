# UART daemon 다중 인스턴스 실행 가이드

## 목적

이 문서는 하나의 host에서 여러 UART daemon을 동시에 실행하는 방법을 정리한다.
예를 들어 Windows host에서 `COM7`은 TCP `17001`, `COM11`은 TCP `17003`으로 각각 독립 실행할 수 있다.

```text
COM7  -> uartd.py instance A -> TCP 0.0.0.0:17001
COM11 -> uartd.py instance B -> TCP 0.0.0.0:17003
```

핵심 원칙은 다음과 같다.

```text
1. UART port는 인스턴스마다 달라야 한다.
2. TCP port는 인스턴스마다 달라야 한다.
3. pid/log/socket 파일도 인스턴스마다 달라야 한다.
```

이번 수정본의 `uartd.py`는 `--port`와 `--tcp` 또는 `--tcp-port`를 기준으로 pid/log/socket 기본 파일명을 자동 분리한다.
따라서 아래처럼 `COM port`와 `TCP port`만 다르게 주면 N개 인스턴스를 실행할 수 있다.

---

## 수정된 동작 요약

### 기존 문제

기존 구조에서는 여러 인스턴스를 실행할 때 기본 파일 경로가 겹칠 수 있었다.

```text
logs/uartd.pid
logs/runtime_log
logs/uartd.log
logs/uartd.sock
```

두 개 이상의 daemon이 같은 파일을 공유하면 다음 문제가 생긴다.

- pid file이 마지막 실행 인스턴스로 덮어써짐
- runtime log가 여러 UART 출력으로 섞임
- daemon log가 섞임
- Linux/WSL에서는 Unix socket path 충돌 가능
- `--tcp 0.0.0.0:PORT`로 bind한 경우 readiness check가 `0.0.0.0`으로 접속하려 해서 실패 가능

### 수정 후

수정본은 명시적인 `--pid-file`, `--runtime-log`, `--daemon-log`, `--socket`이 없으면 자동으로 인스턴스별 파일명을 만든다.

예:

```text
COM7 + TCP 17001
  logs/uartd-COM7-17001.pid
  logs/runtime_log-uartd-COM7-17001
  logs/uartd-COM7-17001.log

COM11 + TCP 17003
  logs/uartd-COM11-17003.pid
  logs/runtime_log-uartd-COM11-17003
  logs/uartd-COM11-17003.log
```

Linux/WSL에서 Unix socket을 함께 사용할 경우에도 기본 socket path가 인스턴스별로 분리된다.

```text
logs/uartd-dev-ttyUSB0-17001.sock
logs/uartd-dev-ttyUSB1-17003.sock
```

---

## Windows PowerShell 사용 예

### COM7 daemon 시작

```powershell
py uartd.py start --port COM7 --baud 115200 --tcp 0.0.0.0:17001
```

### COM11 daemon 시작

```powershell
py uartd.py start --port COM11 --baud 115200 --tcp 0.0.0.0:17003
```

`0.0.0.0`은 모든 네트워크 인터페이스에 bind한다는 뜻이다.
클라이언트가 접속할 때는 `0.0.0.0`이 아니라 실제 접속 가능한 주소를 사용한다.

로컬 PowerShell에서 접속:

```powershell
py uartctl.py --tcp 127.0.0.1:17001 status
py uartctl.py --tcp 127.0.0.1:17001 attach

py uartctl.py --tcp 127.0.0.1:17003 status
py uartctl.py --tcp 127.0.0.1:17003 attach
```

다른 PC 또는 WSL/Linux에서 Windows host로 접속:

```bash
python3 uartctl.py --tcp 192.168.0.170:17001 status
python3 uartctl.py --tcp 192.168.0.170:17001 attach

python3 uartctl.py --tcp 192.168.0.170:17003 status
python3 uartctl.py --tcp 192.168.0.170:17003 attach
```

### daemon 상태 확인

각 인스턴스는 TCP endpoint로 구분해서 확인한다.

```powershell
py uartd.py status --tcp 127.0.0.1:17001
py uartd.py status --tcp 127.0.0.1:17003
```

또는 `uartctl.py`로 확인한다.

```powershell
py uartctl.py --tcp 127.0.0.1:17001 status
py uartctl.py --tcp 127.0.0.1:17003 status
```

### daemon 정상 종료

```powershell
py uartd.py stop --tcp 127.0.0.1:17001
py uartd.py stop --tcp 127.0.0.1:17003
```

또는 `uartctl.py`로 종료한다.

```powershell
py uartctl.py --tcp 127.0.0.1:17001 stop
py uartctl.py --tcp 127.0.0.1:17003 stop
```

### Windows 프로세스 확인

```powershell
Get-CimInstance Win32_Process |
  Where-Object { $_.CommandLine -match "uartd\.py" } |
  Format-Table ProcessId, CommandLine -AutoSize
```

### Windows 프로세스 강제 종료

정상 종료가 안 될 때만 사용한다.

```powershell
Get-CimInstance Win32_Process |
  Where-Object { $_.CommandLine -match "uartd\.py" } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
```

특정 TCP port 인스턴스만 종료하고 싶으면 command line으로 필터링한다.

```powershell
Get-CimInstance Win32_Process |
  Where-Object { $_.CommandLine -match "uartd\.py" -and $_.CommandLine -match "17001" } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
```

---

## Linux / WSL 사용 예

### /dev/ttyUSB0 daemon 시작

```bash
python3 uartd.py start --port /dev/ttyUSB0 --baud 115200 --tcp 0.0.0.0:17001
```

### /dev/ttyUSB1 daemon 시작

```bash
python3 uartd.py start --port /dev/ttyUSB1 --baud 115200 --tcp 0.0.0.0:17003
```

Linux/WSL에서는 기본적으로 Unix socket과 TCP가 함께 열린다.
TCP만 사용하려면 `--no-unix-socket`을 추가한다.

```bash
python3 uartd.py start --port /dev/ttyUSB0 --baud 115200 --tcp 0.0.0.0:17001 --no-unix-socket
python3 uartd.py start --port /dev/ttyUSB1 --baud 115200 --tcp 0.0.0.0:17003 --no-unix-socket
```

### 상태 확인

```bash
python3 uartd.py status --tcp 127.0.0.1:17001
python3 uartd.py status --tcp 127.0.0.1:17003
```

또는:

```bash
python3 uartctl.py --tcp 127.0.0.1:17001 status
python3 uartctl.py --tcp 127.0.0.1:17003 status
```

### attach

```bash
python3 uartctl.py --tcp 127.0.0.1:17001 attach
python3 uartctl.py --tcp 127.0.0.1:17003 attach
```

### 종료

```bash
python3 uartd.py stop --tcp 127.0.0.1:17001
python3 uartd.py stop --tcp 127.0.0.1:17003
```

---

## 명시적 로그 경로를 직접 지정하는 방법

자동 파일명을 쓰지 않고 직접 경로를 지정할 수도 있다.

```powershell
py uartd.py start `
  --port COM7 `
  --baud 115200 `
  --tcp 0.0.0.0:17001 `
  --pid-file logs\uartd-com7.pid `
  --runtime-log logs\runtime-com7.log `
  --daemon-log logs\uartd-com7.log
```

```powershell
py uartd.py start `
  --port COM11 `
  --baud 115200 `
  --tcp 0.0.0.0:17003 `
  --pid-file logs\uartd-com11.pid `
  --runtime-log logs\runtime-com11.log `
  --daemon-log logs\uartd-com11.log
```

일반적으로는 명시하지 않아도 된다. 수정본이 자동으로 분리한다.

---

## 방화벽 확인

Windows에서 `0.0.0.0:17001`처럼 외부 접속 가능하게 bind하면 Windows Defender Firewall에서 Python 또는 해당 TCP port 접근을 허용해야 할 수 있다.

로컬 접속만 필요하면 `127.0.0.1` bind를 권장한다.

```powershell
py uartd.py start --port COM7 --baud 115200 --tcp 127.0.0.1:17001
```

다른 장비에서 접속해야 하면:

```powershell
py uartd.py start --port COM7 --baud 115200 --tcp 0.0.0.0:17001
```

클라이언트에서는 Windows host의 실제 IP를 사용한다.

```bash
python3 uartctl.py --tcp 192.168.0.170:17001 status
```

---

## 점검 순서

### 1. daemon 프로세스 확인

Windows:

```powershell
Get-CimInstance Win32_Process |
  Where-Object { $_.CommandLine -match "uartd\.py" } |
  Format-Table ProcessId, CommandLine -AutoSize
```

Linux/WSL:

```bash
pgrep -af uartd.py
```

### 2. TCP listen 확인

Windows:

```powershell
netstat -ano | findstr ":17001"
netstat -ano | findstr ":17003"
```

Linux/WSL:

```bash
ss -ltnp | grep -E '17001|17003'
```

### 3. uartd status 확인

```powershell
py uartd.py status --tcp 127.0.0.1:17001
py uartd.py status --tcp 127.0.0.1:17003
```

### 4. uartctl attach 확인

```powershell
py uartctl.py --tcp 127.0.0.1:17001 attach
py uartctl.py --tcp 127.0.0.1:17003 attach
```

---

## 주의사항

- `--tcp 0.0.0.0:PORT`는 bind용 주소다. 클라이언트 접속에는 `127.0.0.1` 또는 Windows host의 실제 IP를 사용한다.
- 같은 COM port를 두 daemon이 동시에 열 수 없다.
- 같은 TCP port를 두 daemon이 동시에 listen할 수 없다.
- 다른 프로그램이 COM port를 열고 있으면 `uartd.py`가 해당 port를 열 수 없다.
- 원격 접속을 열 경우 방화벽과 네트워크 보안 정책을 확인한다.
- 여러 daemon을 실행할 때는 각 인스턴스별 runtime log를 확인한다.

---

## 빠른 실행 예

Windows PowerShell:

```powershell
py uartd.py start --port COM7 --baud 115200 --tcp 0.0.0.0:17001
py uartd.py start --port COM11 --baud 115200 --tcp 0.0.0.0:17003

py uartctl.py --tcp 127.0.0.1:17001 status
py uartctl.py --tcp 127.0.0.1:17003 status

py uartctl.py --tcp 127.0.0.1:17001 attach
py uartctl.py --tcp 127.0.0.1:17003 attach
```

Linux/WSL:

```bash
python3 uartd.py start --port /dev/ttyUSB0 --baud 115200 --tcp 0.0.0.0:17001
python3 uartd.py start --port /dev/ttyUSB1 --baud 115200 --tcp 0.0.0.0:17003

python3 uartctl.py --tcp 127.0.0.1:17001 status
python3 uartctl.py --tcp 127.0.0.1:17003 status

python3 uartctl.py --tcp 127.0.0.1:17001 attach
python3 uartctl.py --tcp 127.0.0.1:17003 attach
```
