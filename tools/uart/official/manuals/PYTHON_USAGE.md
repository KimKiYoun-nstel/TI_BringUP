# Python으로 UART Tool 사용하기

## 1. 준비와 파일 선택

배포의 `python/` 폴더를 열고 PowerShell에서 아래 명령을 실행합니다.
Python 3.13에서 확인했으며, USB-UART 드라이버는 장치가 연결된 PC에 설치합니다.
`python --version`으로 Python 설치를 확인하세요.

| 목적 | 함께 필요한 파일 | 설치할 외부 패키지 |
|---|---|---|
| UART 서버 | `uartd.py`, `uart_runtime.py` | pySerial |
| CLI / attach 터미널 | `uartctl.py`, `uart_api.py` | 없음 |
| Manager GUI | `uartgui.py`, `uart_api.py` | PySide6 |
| GUI에서 로컬 서버 시작 | GUI 파일 + `uartd.py`, `uart_runtime.py` | PySide6, pySerial |
| Python API 호출 | `uart_api.py` | 없음 |
| MCP 연동 | `uart_mcp.py`, `uart_api.py` | mcp |

각 `.py`의 역할은 위와 같습니다. `uart_runtime.py`와 `uart_api.py`는 다른 파일이 import하는
모듈이므로 단독으로 실행하지 않습니다. `README.md`는 빠른 안내, `VERSION`은 애플리케이션 버전입니다.
다른 PC의 서버에 접속만 할 때는 그 PC의 COM 드라이버나 pySerial이 필요하지 않습니다.

필요한 패키지만 설치합니다. GUI에서 로컬 서버까지 사용하려면:

```powershell
python -m pip install "pyserial>=3.5,<4" "PySide6>=6.8,<7"
python uartgui.py
```

CLI/API만 쓸 때는 pip 설치가 필요 없습니다. MCP를 쓸 때만 추가합니다:

```powershell
python -m pip install "mcp>=1.26,<2"
```

패키지 설치와 실행에 같은 Python을 사용하세요. `ModuleNotFoundError: serial`이면 pySerial,
`PySide6`이면 PySide6, `mcp`이면 mcp를 해당 Python에 설치합니다.

## 2. GUI 없이 서버·CLI 사용

서버는 장치 PC에서 실행합니다. 한 서버는 UART 한 개를 담당하며 여러 장치에는 서로 다른
TCP 포트와 인스턴스 이름을 사용합니다. 다음은 인증 없는 로컬 전용 예입니다.

```powershell
python -m pip install "pyserial>=3.5,<4"
python uartd.py start --no-serial --no-unix-socket --instance-id board-a --tcp 127.0.0.1:17001
python uartctl.py --tcp 127.0.0.1:17001 status
python uartctl.py --tcp 127.0.0.1:17001 ports
# ports 결과를 보고 실제 COM으로 변경
python uartctl.py --tcp 127.0.0.1:17001 port COM7 --baud 115200
python uartctl.py --tcp 127.0.0.1:17001 attach
```

`attach`는 키를 UART로 전달합니다. **Ctrl-] 다음 q**로 접속만 종료합니다.
읽기 전용은 `watch`이며 Ctrl+C로 종료합니다. GUI·CLI·API는 서버에 TCP로 접속하고 COM을 직접 열지 않습니다.
Manager를 닫거나 attach를 끝내도 서버는 계속 실행됩니다.

```powershell
# 서버 종료: 모든 클라이언트의 접속도 종료됨
python uartctl.py --tcp 127.0.0.1:17001 stop
```

`start`는 백그라운드 실행 후 돌아오고 `run`은 현재 콘솔에서 실행합니다.
기본 수신/데몬 로그는 `.py` 옆 `logs/`에 생성되며 `status`에서 실제 경로를 확인할 수 있습니다.

## 3. Manager 사용

```powershell
python uartgui.py
```

1. 새 로컬 서버: **이 PC에 서버 실행** → 이름·TCP 포트·Local/External·비밀번호 설정.
2. 이미 실행 중인 서버: **서버 주소 등록** → 실제 `IP:포트` 입력 → 필요하면 비밀번호 입력·접속 확인.
3. 장치 목록에서 COM·Baud 선택 → **장치 연결**.
4. **Enter 전송**으로 실제 응답 확인 후 명령 입력.

로컬 서버를 GUI에서 시작하려면 `uartd.py`와 `uart_runtime.py`가 같은 폴더에 있어야 합니다.
주소록은 Windows 사용자 레지스트리에 저장하고 비밀번호는 실행 중 메모리에만 보관합니다.
화면·출력 ON/OFF·COM 변경·오류 해결은 [사용자 가이드](USER_GUIDE.md)를 참고하세요.

## 4. 원격 접속과 인증

아래는 서버/클라이언트가 각각 실행할 명령입니다. 공유 비밀번호는 본인의 값으로 바꿉니다.

```powershell
# 서버 PC
$env:UARTD_TOKEN = "YOUR_SHARED_PASSWORD"
python uartd.py start --no-serial --no-unix-socket --instance-id board-a --tcp 0.0.0.0:17001

# 클라이언트 PC (실제 서버 IP로 변경)
$env:UARTD_TOKEN = "YOUR_SHARED_PASSWORD"
python uartctl.py --tcp 192.168.0.170:17001 status
```

External 바인딩은 공백 제거 후 4자 이상의 공유 비밀번호가 필수입니다. 클라이언트 주소로
`0.0.0.0`을 쓰지 않습니다. 필요하면 `--token-file`로 UTF-8 토큰 파일을 지정할 수 있습니다.
TCP에는 내장 TLS가 없으므로 원격 접속 환경은 [사용자 가이드](USER_GUIDE.md)의 네트워크 안내를 따릅니다.

## 5. Python 코드에서 호출

자동화 코드와 같은 폴더에 `uart_api.py`를 놓습니다. 이미 실행 중인 서버를 대상으로 합니다.

```python
import os
from uart_api import request, require_ok, UARTAPIError

endpoint = "127.0.0.1:17001"
token = os.environ.get("UARTD_TOKEN", "")
try:
    status = require_ok(request(endpoint, {"action": "status"}, token=token))
    print(status)
    # text/expect는 실제 장치 명령과 프롬프트로 변경
    result = require_ok(request(endpoint, {
        "action": "send_expect", "text": "help", "expect": ">",
        "timeout": 10, "newline": True,
    }, token=token, timeout=16))
    print(result["output"])
    if result.get("truncated"):
        print("결과가 길어 최신 부분만 반환되었습니다.")
except UARTAPIError as exc:
    print(f"UART 작업 실패: {exc}")
```

`send_expect`는 기본 독점 송신 보호를 사용합니다. 기존 RW attach나 다른 명령이 있으면
거부될 수 있으므로 RO `watch`를 사용하거나 작업을 마친 뒤 명령을 실행합니다.
timeout이어도 송신은 이미 됐을 수 있으니 자동 재전송하지 마세요.
전체 명령·오류·응답 제한은 [TCP API](PROTOCOL.md), 에이전트 등록은 [MCP 안내](MCP.md)에 있습니다.
