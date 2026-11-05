# UART Tool — Python 실행 파일

모든 기능의 구현 원본은 이 폴더의 Python 소스입니다. EXE는 같은 소스를 런타임과 묶은 실행 대안입니다.

| 필요한 기능 | 필요한 파일 / 의존성 |
|---|---|
| UART 서버 | uartd.py + uart_runtime.py / pySerial |
| CLI·터미널 | uartctl.py + uart_api.py / Python 표준 라이브러리 |
| Manager GUI | uartgui.py + uart_api.py / PySide6 |
| GUI에서 로컬 서버 실행 | 위 GUI 구성 + 같은 폴더의 uartd.py·uart_runtime.py |
| Python API | uart_api.py / Python 표준 라이브러리 |
| MCP 브리지 | uart_mcp.py + uart_api.py / mcp |

```powershell
python -m pip install "pyserial>=3.5,<4" "PySide6>=6.8,<7"
python uartgui.py
# GUI 없이 서버·CLI 사용
python uartd.py start --no-serial --no-unix-socket --instance-id board-a --tcp 127.0.0.1:17001
python uartctl.py --tcp 127.0.0.1:17001 status
```

Python 3.13에서 확인했습니다. 필요한 기능의 의존성만 설치하면 됩니다.
CLI/API만 쓰면 외부 패키지는 필요 없습니다. MCP는 `python -m pip install "mcp>=1.26,<2"`로 설치합니다.
GUI에서 로컬 서버를 시작할 때는 pySerial도 필요합니다. EXE와 Python을 둘 다 실행할 필요는 없습니다.
VERSION은 애플리케이션 버전입니다. 같은 COM을 여러 서버로 동시에 열지 마세요.
설치·실행·인증·API 예제: [Python 사용법](../manuals/PYTHON_USAGE.md)
화면·CLI 조작: [사용자 가이드](../manuals/USER_GUIDE.md)
