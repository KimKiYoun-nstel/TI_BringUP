# 공식 UART Tool 배포본 갱신

## 관리 경계

- `official/python/`, `official/manuals/`: 공식 배포본을 원형으로 반입한다.
- `integration/`: repo 전용 CLI wrapper, target 해석, MCP와 bring-up 기능.
- `config/targets.json`, `.secrets/`: 이 repo의 접속 설정과 로컬 인증 파일.

공식 MCP는 예제이며 이 repo MCP와 함께 교체하지 않는다.
공식 소스는 ZIP이 아닌 Python·문서 파일 자체를 Git으로 관리한다.
파일별 해시나 manifest를 생성·유지·검사하지 않는다.

## 갱신 절차

1. 새 공식 배포본의 `python/`, `manuals/`를 각각 `official/` 아래에 교체한다.
   삭제된 파일도 반영하며 기존·신규 버전을 섞지 않는다.
2. 두 `VERSION`과 배포 README·PROTOCOL·PYTHON_USAGE를 읽고 API/인자 변경을 검토한다.
   현재 두 VERSION은 모두 `0.1.0-dev`이므로 변경 내용은 Git diff와 배포 설명도 함께 본다.
3. 공식 코드를 repo 용도로 수정하지 않는다. 필요한 적응은 `integration/`에 반영한다.
   특히 공식 daemon은 `uart_runtime.py`, CLI는 `uart_api.py`를 함께 필요로 한다.
4. 다음 로컬 테스트와 MCP 등록 확인을 수행한다.

   ```bash
   python3 -B -m unittest discover -s tests/tools/uart -v
   opencode mcp list
   ```

5. 두 target에 `status`, MCP `uart_tail`을 실행하고, 콘솔 프롬프트를 확인한 뒤
   `uname -n` 같은 간단한 명령으로 송수신을 검증한다. timeout이면 tail로 결과를 확인한다.
   CLI `tail`은 지속 구독이므로 수신 확인 후 `Ctrl-C`로 종료한다.
6. 변경한 버전·경로·실측 결과를 bring-up 로그에 기록한다. MCP 설정이나 서버 코드가
   바뀌면 OpenCode를 종료 후 재시작하여 도구 목록과 연결을 다시 확인한다.

로컬 소스 갱신은 원격 PC의 daemon을 배포·재시작하지 않는다.
원격 서버 변경은 공식 프로젝트의 배포 절차로 별도 수행한다.

## 현재 반입 기준

2026-11-05 사용자가 제공한 새 `manuals/`, `python/` 두 폴더를 기준으로 반입했다.
예전 `upstream/`의 중복 소스·문서·테스트, 파일 해시 관리 코드는 제거했다.
새 공식 배포본에는 테스트 묶음이 없으므로 repo의 `tests/tools/uart/`로 연동을 검증한다.
