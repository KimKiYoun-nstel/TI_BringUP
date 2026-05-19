# SK-AM64B RPMsg 테스트 프로젝트

이 디렉터리는 SK-AM64B 보드에서 **A53 Linux userspace 테스트 클라이언트**와 **R5F(`r5fss0-0`) firmware** 사이의 RPMsg 통신을 검증하기 위한 repo 관리형 재사용 프로젝트를 담는다.

## 목적

- `r5fss0-0`에 올릴 테스트용 firmware를 repo 안에서 관리한다.
- A53 Linux에서 실행할 테스트용 userspace 클라이언트를 repo 안에서 관리한다.
- 설치된 SDK/툴체인을 재사용해서 빌드한다.
- 실제 보드에 올려 RPMsg payload 왕복이 되는지 검증한다.

## 중요한 개념

- A53 쪽 프로그램은 **지속 실행 daemon/service가 아니라 단발 실행형 테스트 클라이언트**다.
- 기존 `benchmark_server.service`, `rpmsg_json.service`는 **이번 프로젝트와 별개인 TI benchmark baseline 서비스**다.
- 이번 프로젝트는 기존 benchmark 기능을 대체하지 않는다.
- 다만 benchmark baseline도 `rpmsg_chrdev` 기반 RPMsg 채널을 사용하므로, 테스트 firmware 적용 시에는 관련 서비스를 중지해야 한다.

## 구조

```text
projects/sk-am64b-rpmsg-test/
  README.md
  docs/
    plan.md                  # 계획 문서
    board-apply.md           # 보드 적용/검증 절차
    completion.md            # 완료 결과
    issues.md                # 기억해야 할 이슈
  board/
    sk-am64b-rpmsg-manage.sh # 보드 내부 적용/복구 스크립트
  r5f/
    example.syscfg
    main.c
    ipc_rpmsg_echo.c
    ti-arm-clang/
      example.projectspec
  a53/
    Makefile
    src/
      main.c
```

## 빌드

```bash
./tools/build/build-sk-am64b-rpmsg-test.sh r5f
./tools/build/build-sk-am64b-rpmsg-test.sh a53
./tools/build/build-sk-am64b-rpmsg-test.sh all
```

빌드 결과는 `out/sk-am64b-rpmsg-test/` 아래에 생성된다.

## Host 배포

```bash
./tools/install/deploy-sk-am64b-rpmsg-host.sh 192.168.0.110
```

이 단계는 Host에서 보드로 다음 파일만 복사한다.

- 테스트 firmware 파일
- A53 테스트 클라이언트
- 보드 내부 적용/복구 스크립트

이 단계에서는 **활성 firmware symlink를 바꾸지 않는다.**

## 보드 내부 적용 / 테스트 / 복구

보드에서 직접 또는 SSH로 다음 스크립트를 실행한다.

```bash
/usr/local/sbin/sk-am64b-rpmsg-manage.sh apply
/usr/local/sbin/sk-am64b-rpmsg-manage.sh test "payload-from-a53"
/usr/local/sbin/sk-am64b-rpmsg-manage.sh restore
```

자세한 절차는 [docs/board-apply.md](/home/nstel/ti/TI_Bringup/projects/sk-am64b-rpmsg-test/docs/board-apply.md)를 따른다.

## 문서 언어

이 프로젝트 아래 문서는 repo 전체 원칙에 따라 한글을 기본으로 사용한다.
