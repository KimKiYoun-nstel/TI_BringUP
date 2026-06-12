# 2026-06-02 R5F Remoteproc IPC-only Inventory

## 목적

이 문서는 현재 local Linux kernel workspace가
`SBL이 먼저 실행한 R5F firmware`에 대해
attach 또는 IPC-only 성격의 동작을 지원할 가능성이 있는지 정리한다.

이 단계에서는 코드를 수정하지 않고,
source 상의 근거와 기존 bring-up 기록만 inventory 한다.

## 확인한 source 근거

### 1. remoteproc 공통 interface에 attach / detach / loaded resource table hook 존재

파일:

- `workspace/ti-linux-kernel-sdk12/include/linux/remoteproc.h`

확인 내용:

- `attach`
- `detach`
- `get_loaded_rsc_table`
- `RPROC_DETACHED`

의미:

- remote processor가 외부 entity에 의해 이미 기동된 경우,
  Linux가 단순 load/start 외의 attach path를 가질 수 있다.

### 2. TI K3 R5 remoteproc driver에 IPC-only mode detection 존재

파일:

- `workspace/ti-linux-kernel-sdk12/drivers/remoteproc/ti_k3_r5_remoteproc.c`

확인 내용:

- driver 주석에 `IPC-only mode`가 명시됨
- core가 bootloader에 의해 이미 load/start 된 경우를 감지한다고 설명
- 조건 충족 시 `configured R5F for IPC-only mode` 로그 경로 존재
- `rproc->state = RPROC_DETACHED`
- `attach = k3_rproc_attach`
- `detach = k3_rproc_detach`
- `get_loaded_rsc_table = k3_get_loaded_rsc_table`

의미:

- 현재 local kernel은 단순한 firmware load/start 전용 driver가 아니다.
- 문서상 목표인

```text
SBL이 먼저 실행한 R5F
  -> Linux가 attach / IPC-only로 인식
```

경로와 직접 연결되는 코드 흔적이 이미 존재한다.

## 기존 repo bring-up 기록과의 관계

관련 문서:

- `docs/bringup-logs/2026-05-15_sk-am64b_r5f_remoteproc_rpmsg_resolution.md`

기존 live board 검증에서는 다음이 확인되었다.

- `remoteproc1 -> 78000000.r5f`
- `state = running`
- `/dev/rpmsg*`, `/dev/rpmsg_ctrl*` 생성
- `rpmsg_json.service` ordering race 완화 후 userspace round-trip 정상화

이 기록은 현재 kernel/DT/rootfs 조합에서
AM64x R5F remoteproc + RPMsg baseline 자체는 동작한다는 근거다.

## 판단

### 확정된 사실

- local kernel source에는 IPC-only / attach 관련 코드가 존재한다.
- local repo에는 remoteproc/RPMsg baseline 정상 동작의 board-side 기록이 이미 있다.

### 합리적 추정

- 작업 단위 3의 핵심 질문인
  `Linux가 이미 running 중인 R5F에 attach할 수 있는가?`
  는 현재 SDK 12 기준으로 검증 가치가 높다.

### 아직 확인 필요

- 실제 SBL early boot 이후에도 위 조건이 성립하는지
- resource table 위치와 DTS `memory-region`이 attach 조건을 만족하는지
- Linux boot log에서 새 firmware load/start 없이 `detached -> attached` 성격의 흐름이 관찰되는지

## Gate 판단

작업 단위 1의 Gate 기준으로 보면 현재 상태는 다음에 가깝다.

```text
Gate 1-A. local kernel에 attach/IPC-only 지원 흔적 있음
```

따라서 다음 단계는 다음과 같이 잡는 것이 적절하다.

- 작업 단위 2: R5F early boot image 준비 진행 가능
- 작업 단위 3: attach/RPMsg 검증 준비 진행 가치 높음

## 현재 단계에서 하지 않는 것

- Linux remoteproc driver patch 작성
- 보드에서 remoteproc stop/start 실험
- OSPI overwrite

이 문서는 inventory 근거만 정리한다.
