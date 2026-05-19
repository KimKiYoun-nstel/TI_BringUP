# 완료 결과

## 결과 요약

repo 관리형 SK-AM64B RPMsg 테스트 프로젝트를 생성했고, 실제 보드에서 A53 userspace 앱과 R5F firmware 사이의 RPMsg payload 왕복을 검증했다.

최종적으로는 **Host 배포**와 **보드 내부 적용/복구**를 분리한 흐름까지 검증했고, 최종 운영 모델은 **reboot 기반 적용/복구**로 확정했다.

생성된 프로젝트:

- R5F firmware 프로젝트: `projects/sk-am64b-rpmsg-test/r5f`
- A53 Linux userspace 프로젝트: `projects/sk-am64b-rpmsg-test/a53`

추가한 helper:

- 빌드 helper: `tools/build/build-sk-am64b-rpmsg-test.sh`
- Host 배포 helper: `tools/install/deploy-sk-am64b-rpmsg-host.sh`
- 보드 내부 적용/복구 스크립트: `projects/sk-am64b-rpmsg-test/board/sk-am64b-rpmsg-manage.sh`

## 실제 확인한 항목

1. repo 관리형 R5F firmware ELF 빌드 성공
   - `out/sk-am64b-rpmsg-test/ccs_projects/sk_am64b_rpmsg_test_r5fss0_0_freertos_ti_arm_clang/Release/sk_am64b_rpmsg_test_r5fss0_0_freertos_ti_arm_clang.out`
2. repo 관리형 A53 userspace 앱 빌드 성공
   - `out/sk-am64b-rpmsg-test/a53/sk_am64b_rpmsg_test_a53`
3. R5F firmware를 `am64-main-r5f0_0-fw`로 보드에 반영했고 Linux remoteproc가 실제로 로드함
4. A53 userspace 앱이 RPMsg로 payload를 보내고 R5F firmware가 동일 문자열을 echo함
5. 검증 후 기존 benchmark firmware와 서비스 상태를 복구함
6. Host 배포만 수행했을 때는 활성 firmware symlink가 바뀌지 않음을 확인함
7. 보드 내부 `apply` → `test` → `restore` 흐름이 reboot 기반으로 성공함

## End-to-End 성공 출력

A53 userspace 테스트 앱에서 실제로 확인한 출력:

```text
TX: payload-from-a53
RX: payload-from-a53
STATUS: PASS
```

의미:

- A53 앱이 문자열 `payload-from-a53` 전송
- R5F firmware가 동일한 문자열로 echo 응답
- payload 일치 검사 통과

추가 검증 payload:

```text
TX: payload-split-flow
RX: payload-split-flow
STATUS: PASS
```

## 최종 보드 상태

복구 후 확인한 상태:

- `benchmark_server.service`: `active`
- `rpmsg_json.service`: `active`
- `/usr/lib/firmware/mcusdk-benchmark_demo/am64-main-r5f0_0-fw`: benchmark firmware (`86352` bytes)로 복구됨
- 대상 remoteproc 상태: `running`

## 구현 메모

- R5F 테스트 firmware는 Linux IPC를 활성화하고 `rpmsg_chrdev` 서비스(endpoint `14`)를 announce하도록 구성했다.
- A53 테스트 앱은 `libti_rpmsg_char`를 이용해 `R5F_MAIN0_0`에 연결하고, 임의 payload를 전송한 뒤 echo 응답을 검증한다.
- Host 배포는 `/usr/lib/firmware/ti-bringup/sk-am64b-rpmsg-test/` 아래에 테스트 firmware를 저장하고, 보드 내부 스크립트가 활성 symlink 전환을 담당한다.
- runtime stop/start는 현재 보드/SDK 조합에서 운영 경로로 채택하지 않고, reboot 기반 적용을 기본으로 사용한다.
