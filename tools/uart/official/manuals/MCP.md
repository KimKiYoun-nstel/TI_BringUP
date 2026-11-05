# 로컬 에이전트와 MCP 연동

## API와 MCP의 관계

`uartd`는 HTTP/REST 또는 MCP 서버가 아닌 TCP JSON 서버입니다.
에이전트는 `uart_api.py`를 직접 사용하거나 CLI를 실행할 수 있습니다([API 예제](PROTOCOL.md)).
MCP 도구를 사용하는 에이전트에는 이 프로젝트의 **선택 설치형 `uart_mcp.py` stdio 브리지**를 등록합니다.

```text
에이전트 ─ MCP stdio ─ uart_mcp.py ─ TCP JSON ─ uartd ─ UART
사람     ─ Manager GUI ────────────┘
```

브리지는 기존 uartd에 접속합니다. uartd의 시작/설치나 원격 프로세스 재시작은 수행하지 않습니다.
Manager가 열려 있을 필요가 없습니다. 기본 EXE 빌드에는 MCP 브리지를 포함하지 않습니다.

## 설치

배포의 `python/` 폴더에서:

```powershell
python -m pip install "mcp>=1.26,<2"
# 이 PC에서 Python 서버도 실행할 때만 추가 설치
python -m pip install "pyserial>=3.5,<4"
python uartd.py start --no-serial --no-unix-socket --instance-id agent --tcp 127.0.0.1:17001
```

이미 같은 주소에서 데몬이 동작하면 두 번째 명령은 생략합니다.

## MCP 클라이언트 등록 예제

다음은 `mcpServers` 형식을 사용하는 클라이언트의 일반 예제입니다.
실제 설정 파일 위치와 최상위 키는 사용하는 에이전트의 MCP 설정 규칙에 맞추세요.
경로를 자신의 Python 실행 파일과 배포 `python/` 폴더의 절대 경로로 교체합니다.
`python -c "import sys; print(sys.executable)"`로 사용하는 Python 경로를 확인할 수 있습니다.

```json
{
  "mcpServers": {
    "uartd": {
      "command": "C:\\YOUR_PYTHON\\python.exe",
      "args": ["D:\\UART_TOOL\\python\\uart_mcp.py"],
      "env": {
        "UARTD_ENDPOINT": "127.0.0.1:17001"
      }
    }
  }
}
```

인증 사용 시 `env`에 `"UARTD_TOKEN_FILE": "D:\\secrets\\uartd.token"`을 추가합니다.
원격 서버라면 `UARTD_ENDPOINT`를 서버 IP:포트로 변경합니다.
파일은 **브리지가 실행되는 PC**에 있어야 하며 서버와 같은 토큰을 담습니다.
`UARTD_TOKEN`도 지원하지만 파일 설정을 권장합니다. 둘 다 있으면 파일이 우선입니다.
토큰은 도구 인자로 노출하지 않으며 stdout에는 MCP 메시지만 출력합니다.

## 제공 도구

| MCP 도구 | 인자 | uartd action |
|---|---|---|
| `uart_status` | 없음 | `status` |
| `uart_list_ports` | 없음 | `list_ports` |
| `uart_set_port` | `port`, `baud=115200`, `force=false` | `set_port` |
| `uart_disconnect` | `force=false` | `disconnect_port` |
| `uart_baud` | `baud` | `baud` |
| `uart_send` | `text`, `newline=false` | `send` |
| `uart_command` | `text`, `expect`, `timeout=10`, `newline=true` | `send_expect` |
| `uart_tail` | `lines=80` | `tail_once` |

도구 결과는 API 성공 응답의 필드들을 반환합니다. 통신 오류 또는 `ok:false`는 MCP 도구 오류입니다.
`uart_command.timeout`은 0~120초, `uart_tail.lines`는 1~1000입니다.
stdio 브리지는 짧은 요청/응답 도구를 제공합니다. raw `attach`, 무한 `tail` 스트림,
별도의 `expect`, 데몬 `stop`은 이 브리지의 도구로 노출하지 않습니다. 필요하면 TCP/CLI를 이용하세요.

## 에이전트 운용 순서

1. `uart_status`로 대상과 연결 상태 확인.
2. `uart_list_ports`로 실제 서버의 장치 확인.
3. 필요한 경우 `uart_set_port(port="COM11", baud=115200)`.
4. `uart_command(text="help", expect=">", timeout=10)`처럼 보드에 맞는 명령 실행.
5. `uart_tail`로 최근 로그 확인. `expect`는 정규식이 아닌 리터럴 부분 문자열입니다.

timeout 응답이더라도 송신은 이미 일어났을 수 있습니다. 변경 명령을 자동 재전송하지 마세요.
RW 터미널과 에이전트가 같은 UART에 쓸 수 있으므로 장치별 명령을 직렬화합니다.
COM 변경은 전체 클라이언트에 영향을 주며 `force`는 명시적으로 선택합니다.

## 장치 없이 연결 점검

테스트용 별도 데몬을 `127.0.0.1:17009`에서 `--port loop://`로 시작한 뒤 브리지 endpoint를 맞춥니다.
에이전트의 도구 목록에 8개 `uart_*`가 나타나는지 확인하고,
`uart_command(text="ping", expect="ping")` 결과에 `matched: "ping"`이 있는지 확인합니다.
실제 COM 하드웨어와 사용하는 에이전트 UI에서의 등록은 각각 별도 검증해야 합니다.
