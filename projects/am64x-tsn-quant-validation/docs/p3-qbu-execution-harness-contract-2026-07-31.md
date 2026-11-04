# P3 Qbu/IET Execution Harness Contract

## 목적

P3 traffic 결과와 host/UART/SSH orchestration failure를 분리한다. board traffic을 반복하기
전에 실행 harness가 bounded operation, 상태 기록, failure stop을 보장해야 한다.

## 단계

1. **Preflight**: live 1 Gbps/full link와 clean idle state를 확인하고 direct test IP를 준비한다.
2. **Stage**: endpoint runner를 TMDS와 SK UART에 campaign 최초 1회만 배치한다. compressed
   base64 payload를 512-byte UART input chunk로 전송하고 target-side SHA-256으로 검증한다.
3. **Measurement**: stage된 endpoint runner만 사용해 control, baseline, matrix case를 실행한다.
   case 중 file transfer나 deployment를 반복하지 않는다. receiver `iperf3` UDP listener가
   `/proc/net/udp`에서 5002/5003 listen 상태가 된 뒤 sender를 시작한다.
4. **Collect and reset**: raw artifact는 cleanup 후 host SSH bulk transfer로 회수한다. SK
   artifact는 TMDS를 경유하되 target-side `/bin/timeout 60`과 host-side 총 90-second timeout을
   적용한다. cleanup이 TMDS management `eth0`을 복구하는 동안 connection이 즉시 가능하지 않을 수
   있으므로 이 bound 안에서 collection을 재시도한다. 회수 성공 또는 실패 뒤 data-port test IP를
   제거한다.

P3 board control과 stage에는 host SSH, TMDS control IP, TMDS->SK nested SSH를 사용하지
않는다. UART daemon이 두 board의 유일한 control transport다. SSH는 traffic 종료와 cleanup
후 raw artifact를 PC로 옮기는 bounded bulk-transfer 용도에만 사용한다.

TMDS management address가 DHCP로 변할 수 있으므로 artifact collector는 cleanup 뒤 UART로 `eth0`을
up하고 current IPv4 address를 발견한 뒤 bounded SSH transfer를 시작한다. 실제 endpoint는
`artifact-transport.json`에 기록한다. `P3_TMDS_SSH_HOST`는 legacy manifest hint로만 남긴다.

## Failure Contract

- host-side per-run timeout은 traffic duration + 600 seconds다.
- per-run runner exit code가 0이 아니면 `campaign-record.json`을 먼저 저장하고 campaign을 즉시
  중단한다. 다음 case를 실행하지 않는다.
- control 또는 accepted golden baseline gate가 실패하면 같은 방식으로 즉시 중단한다.
- `campaign-status.json`은 `running`, `failed`, `completed` 상태와 current case/repeat를 기록한다.
  진행 상태 확인은 console wait가 아니라 이 file과 board UART process/MM state를 기준으로 한다.

## 운영 원칙

measurement campaign은 새로운 profile을 발견할 때만 실행한다. 이미 얻은 result의 재해석,
runner 안정화, artifact review는 board traffic 없이 먼저 완료한다. incomplete campaign artifact는
실패 증적으로 보존하되 summary 결과에 합산하지 않는다.
