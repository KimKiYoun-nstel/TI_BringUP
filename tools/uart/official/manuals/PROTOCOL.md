# uartd TCP JSON API

GUI 없이 로컬/원격 에이전트에서 사용할 수 있는 API입니다. HTTP/REST가 아니므로
`curl http://...`로 호출하지 않습니다. GUI도 동일한 API를 사용합니다.
EXE 배포에서는 `uartd.exe`가 이 API 서버입니다. `uart-manager.exe`나 `uartctl.exe`는
API 호출에 필수 요소가 아닙니다. 파일별 실행·배치는 [사용자 가이드](USER_GUIDE.md)를 참고하세요.
서버 시작·인증 준비는 [사용자 매뉴얼](USER_GUIDE.md), MCP 등록은 [MCP 안내](MCP.md)를 참고하세요.

## 1. 전송 규칙

TCP `HOST:PORT`에 연결한 후 UTF-8 JSON 객체 하나를 한 줄(`\n`)로 전송한다. 제어 명령의 응답도 JSON 한 줄이다. `attach` 성공 응답 이후 같은 소켓은 원시 UART 바이너리 스트림으로 전환된다. `tail` 성공 응답 이후는 계속 JSON 이벤트를 수신한다.

인증 설정이 있다면 모든 JSON 요청에 `"token":"..."` 필드를 추가한다. `uartctl`에서는 `--token-file` 또는 `UARTD_TOKEN` 환경 변수를, GUI에서는 접속 비밀번호 입력란을 사용한다. 설정된 토큰은 공백 제거 후 4자 이상이어야 한다. **토큰은 평문 TCP를 통과하므로 외부 접속은 VPN 또는 SSH 터널을 사용**한다.

## 2. 신규 API

| 명령 | 요청 필드 | 결과·정책 |
|---|---|---|
| `list_ports` | 없음 | 호스트 PC의 `device`, `description`, `hwid`, `vid`, `pid`, `serial_number` 목록 |
| `set_port` | `port`(필수), `baud`(선택), `force`(선택) | 새 시리얼 열기 성공 후 이전 포트 교체 |
| `disconnect_port` | `force`(선택) | UART만 닫고 TCP 데몬 유지 |

사용 예:

```json
{"action":"list_ports"}
```

```json
{"action":"set_port","port":"COM11","baud":9600,"force":true}
```

```json
{"action":"disconnect_port","force":true}
```

예시 성공 응답:

```json
{"ok":true,"changed":true,"previous_port":"COM7","port":"COM11","baud":9600,"session_generation":3,"attached_clients":2}
```

보호 정책에 의해 거부되면 `{"ok":false,"error":"..."}`가 반환된다. 새 COM 열기 실패 시 활성 시리얼 핸들과 기존 TCP 연결은 유지된다.

## 3. 기존 API

| 명령 | 요청 필드 | 설명 |
|---|---|---|
| `status` | 없음 | 데몬 및 UART 상태, 접속자 수, 로그 경로 |
| `baud` | `baud` | UART 속도 변경, TCP 연결 유지 |
| `send` | `text`, `newline` | UART 문자열 전송 |
| `expect` | `pattern`, `timeout`, `from` 또는 `from_offset` | 지정 문자열 대기 |
| `send_expect` | `text`, `expect`, `timeout`, `newline`, `exclusive` | UART 명령 실행 후 패턴 대기 (`uartctl command`), 기본 독점 송신 보호 |
| `tail_once` | `lines` | 최근 수신 로그 조회 |
| `tail` | `lines` | 최근 로그 후 새 출력 이벤트 지속 수신 |
| `attach` | `mode=rw/ro`, `backlog_lines` | JSON 승인 후 원시 UART 송수신 |
| `stop` | 없음 | 프로세스 정상 종료 |

`status` 추가 필드:

```json
{
  "ok": true,
  "pid": 4312,
  "instance_id": "board-a",
  "port": "COM11",
  "requested_port": "COM11",
  "baud": 9600,
  "serial_state": "connected",
  "last_serial_error": null,
  "session_generation": 3,
  "tcp": "0.0.0.0:17001",
  "rw_attach_clients": 1,
  "ro_attach_clients": 2
}
```

이 예시는 일부 필드만 표시한 것이며 실제 응답은 나머지 기존 항목도 포함한다. USB 연결이 끊어지면 `port=null`, `requested_port`에 마지막 포트명, `serial_state=error`, `last_serial_error`에 오류 메시지가 들어간다.

## 4. 오류 처리

- `unauthorized`: 잘못된/누락된 토큰
- `RW attach clients are connected`: RW 접속자 존재, 명시적 승인 후 `force=true`로 재요청
- `An expect/command is pending`: 명령 대기 중 포트 변경 거부(강제 불가)
- `Failed to open serial port`: 대상 COM에 접근할 수 없음; 기존 COM 유지
- `Serial port not connected`: 연결 해제 상태에서 송수신 불가

`session_generation` 증가 전후에 동일한 `expect` 결과가 섞이지 않도록 내부 검색 버퍼를 초기화한다. 누적 `offset`은 유지된다.

## 5. Python 에이전트에서 직접 사용

프로젝트 폴더에서 실행하거나 `uart_api.py`를 Python import 경로에 둡니다.
클라이언트 모듈 자체는 Python 표준 라이브러리만 사용합니다.
아래 예는 이미 실행 중인 uartd에 접속합니다. COM 이름과 명령/프롬프트는 장치에 맞춰 바꾸세요.

```python
import os
from pathlib import Path
from uart_api import request, require_ok, UARTAPIError

endpoint = "127.0.0.1:17001"
token_file = os.environ.get("UARTD_TOKEN_FILE")
token = (Path(token_file).read_text(encoding="utf-8-sig").strip()
         if token_file else os.environ.get("UARTD_TOKEN", ""))

def call(action, *, socket_timeout=5, **fields):
    return require_ok(request(endpoint, {"action": action, **fields},
                              token=token, timeout=socket_timeout))

try:
    print(call("status"))
    print(call("list_ports"))
    print(call("set_port", port="COM11", baud=115200))
    result = call("send_expect", text="help", expect=">", newline=True,
                  timeout=10, socket_timeout=15)
    print(result["output"])
    print(call("tail_once", lines=80)["text"])
except UARTAPIError as exc:
    print(f"UART 작업 실패: {exc}")
```

`request(endpoint, payload, token="", timeout=3.0)`는 요청마다 새 TCP 연결을 만들고 응답 후 닫습니다.
`ok:false`도 그대로 dict로 반환하므로 `require_ok()`로 검사해야 합니다.
API 함수가 환경 변수/토큰 파일을 자동으로 읽지는 않습니다. 위 예처럼 호출자가 전달합니다.
서버의 대기 `timeout`보다 소켓 timeout을 길게 설정하세요. 특히 기본 3초로 10초 command를 기다릴 수 없습니다.

## 6. 요청 기본값 / 결과 의미

- `send.newline`: 기본 `false`. `send_expect.newline`: 기본 `true`(LF 추가).
  문자열 옵션은 `"lf"`, `"crlf"`, `"cr"`, `"none"`입니다. 실제 개행 문자를 newline 필드에 넣지는 않습니다.
  CR을 직접 보낼 때는 `{"action":"send","text":"\r","newline":false}`처럼 text에 넣을 수 있습니다.
- `expect.pattern` / `send_expect.expect`: 비어 있지 않은 **리터럴 부분 문자열**. 정규식 아님.
- `timeout`: 서버 대기 초, 기본 30, 유한한 수 0~3600(불리언 제외). 일치 실패는 `ok:false`와 오류 응답.
- `expect.from`: 기본 `buffer`(보관 중인 기존 데이터 포함).
  `send_expect.from`: 기본 `now`(송신 직전 이후). `from_offset`이 있으면 우선 적용.
- 성공한 expect 계열: `matched`, `output`, `start_offset`, `end_offset`,
  `match_start_offset`, `match_end_offset`. offset은 수신 텍스트 버퍼의 위치이며 raw 바이트 인덱스로 사용하지 않습니다.
- `send`: `sent`, `shared_write`, `active_attach_clients`. UART worker의 `serial.write`가 전체 바이트를
  수락한 후 ACK합니다. 매 송신에 flush하지 않으므로 물리 전송 완료·보드 명령 성공을 뜻하지 않습니다.
- `list_ports`: `ports` 배열. 장치가 없으면 빈 배열도 정상입니다.
- `tail_once`: `text`, `lines`, `offset`. 기본 200줄, 양수가 아닌 lines도 현재 구현에서는 200줄.
- `attach`: 기본 `mode="rw"`. RO는 읽기 전용. 성공 JSON 후 raw 스트림으로 전환하며
  수신 파서가 JSON 줄 뒤에 이미 읽은 바이트를 버리지 않아야 합니다(`JsonSocketReader.take_remaining()`).
- `tail`: 첫 응답의 `backlog` 이후 JSON 이벤트 스트림. 일반 `request()`는 첫 응답 후 닫으므로
  스트림 수신에는 지속 연결 클라이언트 또는 `uartctl watch`/`attach`를 사용합니다.
  이벤트 형식은 `{"type":"data","data":"UART 수신 텍스트"}`이며, Manager 출력 ON도 이 스트림을 사용합니다.

Baud는 API에서 양의 정수이며 실제 장치/드라이버가 지원해야 합니다. Manager 입력 범위는 300~4000000입니다.
Baud만 바꾸는 요청은 RW attach 연결 중에도 가능하지만 진행 중 expect/command가 있으면 거부됩니다.
COM 교체·해제 시의 `force` 보호와 구분하세요. Baud만 변경할 때는 세션 번호를 증가시키거나 검색 버퍼를 비우지 않습니다.

## 7. 직접 TCP 호출과 재시도 정책

인증이 필요한 status 요청(아래 JSON 뒤에 LF 한 개 필요):

```json
{"action":"status","token":"YOUR_SHARED_TOKEN"}
```

모든 요청은 한 줄 UTF-8 JSON입니다. 요청 ID/HTTP 상태 코드가 없으며 응답의 `ok`와 `error`를 검사합니다.
단발 호출은 한 연결에 한 요청을 사용합니다. JSON 제어 모드는 연결을 유지하고 요청→응답을 순서대로 반복할 수도 있습니다.
요청 ID가 없으므로 하나의 소켓에서 여러 요청을 동시에 처리하지 마세요. Manager 송신 큐는 이 순차 재사용 방식을 씁니다.
데몬 시작은 실행 파일/프로세스 관리 영역입니다. `stop` API 이후에는 서버 PC에서 프로세스를 다시 시작해야 합니다.

읽기 요청은 연결 복구 후 재시도할 수 있습니다. `send`/`send_expect`의 소켓 timeout은
송신되지 않았다는 뜻이 아닙니다. 장치를 변경하는 명령을 맹목적으로 재전송하지 마세요.
여러 클라이언트는 같은 UART를 공유합니다. `send_expect`는 기본 `exclusive=true`로 송신부터
일치/timeout까지 lease를 유지하여 다른 송신·RW attach를 거부합니다. 기존 RW attach나 진행 중 송신/command가
있으면 시작을 거부합니다. RO attach·모니터·status·수동 expect는 가능합니다.
`exclusive=false`를 명시하면 공유 쓰기를 허용하므로 호출자가 명령을 직렬화해야 합니다.
lease는 일치/timeout/클라이언트 종료/장치 오류 때 해제됩니다. 장치 자체의 비동기 출력까지
응답 ID로 구분하거나 요청을 중복 제거하는 기능은 아닙니다.
`session_generation` 변경 시 이전 응답/상태를 다시 확인하세요.

## 8. 자원·응답 한도 (2026-11-05 개선)

| 항목 | 상한 / 동작 |
|---|---|
| 접속 / expect | 클라이언트 64개, 대기 및 예약 쓰기 합산 기준 expect 32개 |
| 최초 요청 | 정상 요청 전 60초 유휴 연결 정리. 이미 요청한 지속 세션/구독은 대상 아님 |
| 요청 / 응답 | 요청 128KiB, JSON 응답 384KiB, 클라이언트 송신 큐 512KiB |
| UART TX | worker 큐 100개, 대기 payload 합계 512KiB. 초과 시 오류 |
| 텍스트 결과 | output/output_since_start/tail/backlog/text/sent 필드별 마지막 48KiB UTF-8 텍스트 유지 |
| tail 범위 | 현재 수신 로그 파일 마지막 48KiB만 읽기. 줄 수 지정은 이 범위 내에서 적용 |
| 로그 | 파일별 10MiB + 백업 3개, 수신 로그 약 250ms 배치 flush |

잘린 응답은 `truncated=true`와 `truncated_fields`(필드별 `original_bytes`, `retained="suffix"`)를
확인하세요. 제어 문자 JSON 이스케이프로 응답 전체가 커지면 추가 축약될 수 있습니다.
`tail_window_bytes`, `tail_window_limited`는 파일 읽기 범위 제한을 별도로 표시합니다.
tail의 첫 줄은 부분 줄일 수 있으며 UTF-8 파일 경계는 대체 문자로 표시될 수 있습니다.
expect의 `matched`/offset은 검색 원본 기준입니다. 반환된 output이 suffix로 잘리면
전체 결과가 아니므로 offset 차이를 문자열 길이로 간주하지 마세요. 페이지 조회 API는 아직 없습니다.

수신 UTF-8은 세션별 incremental decoder로 청크 경계를 보존합니다. COM 변경·오류 시 초기화합니다.
원시 바이너리가 필요하면 text 로그 대신 raw attach를 사용하세요.
`status`는 `command_busy`, `pending_writes`, `limits`도 제공합니다.
쓰기 대기 중 COM/baud 변경은 거부합니다(`force`로 우회하지 않음).
CLI 제어 응답 timeout은 기본 10초(`--response-timeout`), command는 서버 대기+6초 이상을 사용합니다.
attach/watch는 성공 handshake 이후 지속 스트림 대기를 무제한으로 전환합니다.
