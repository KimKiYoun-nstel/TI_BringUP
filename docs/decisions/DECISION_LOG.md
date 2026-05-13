# Decision Log

프로젝트에서 확정한 중요한 판단을 기록합니다.

## 작성 규칙

- “일단 이렇게 하자” 수준이라도 작업 방향에 영향을 주면 기록합니다.
- 결정 이유와 영향 범위를 남깁니다.
- 나중에 바뀔 수 있으면 재검토 조건을 적습니다.

---

## D-001. 프로젝트 지식 저장소를 Git repo로 관리한다

- 날짜: 2026-04-30
- 상태: Accepted
- 배경:
  - ChatGPT Project 안의 대화만으로는 장기 히스토리와 재사용 가능한 가이드를 안정적으로 관리하기 어렵다.
  - 개발자에게 익숙한 Git 기반 변경 이력을 활용한다.
- 결정:
  - `TI_BringUP` repo를 TI AM64x BSP/Board Bring-up 지식 저장소로 사용한다.
- 영향:
  - 대화에서 나온 장기 보관 항목은 Markdown 문서로 승격한다.
  - 보드별 bring-up 기록과 결정사항을 repo에 누적한다.
- 재검토 조건:
  - 문서 규모가 커져 별도 Wiki/문서 시스템이 필요해질 때

## D-002. Host 개발 환경은 Ubuntu 22.04 WSL을 기준으로 시작한다

- 날짜: 2026-04-30
- 상태: Accepted
- 배경:
  - TI SDK/Yocto 계열 빌드 환경은 Ubuntu LTS 기준으로 구성하는 것이 일반적이다.
  - Ubuntu 22.04 WSL 환경 준비가 완료되었다.
- 결정:
  - 초기 빌드/학습 환경은 Ubuntu 22.04 WSL 기준으로 문서화한다.
- 영향:
  - 이후 명령어와 패키지 설치 절차는 Ubuntu 22.04 기준으로 작성한다.
- 재검토 조건:
  - 특정 TI SDK 버전이 다른 Ubuntu 버전을 요구하거나 WSL 제한에 걸릴 때

## D-003. TI SDK source workspace와 patch 기반 repo 운영 정책을 사용한다

- 날짜: 2026-05-13
- 상태: Accepted
- 배경:
  - TI Processor SDK는 U-Boot, Linux kernel, TF-A, OP-TEE, toolchain, rootfs, prebuilt image 등을 포함하는 큰 BSP workspace이다.
  - U-Boot/Linux 전체 source tree를 `TI_BringUP` 원격 repo에 동기화하면 repo가 커지고, TI BSP 업데이트 추적이 어려워진다.
  - 커스텀 보드 BSP 작업은 보통 전체 source tree 수정이 아니라 Device Tree, defconfig, board 설정, rootfs overlay, patch 중심으로 관리하는 것이 적합하다.
  - AI Agent 기반 분석과 빌드 편의성을 위해 로컬에는 source tree가 필요하다.
- 결정:
  - TI Processor SDK 원본은 `~/ti/am64x/ti-processor-sdk-linux-am64xx-evm-12.00.00.07.04` 아래에 reference/build dependency로 유지한다.
  - `TI_BringUP` repo에는 U-Boot/Linux 전체 source tree를 원격 동기화하지 않는다.
  - 로컬 `TI_BringUP/workspace/` 아래에 SDK source tree를 복사 또는 checkout하여 분석/수정/빌드 작업에 사용한다.
  - `workspace/`는 Git 관리 대상에서 제외한다.
  - 의미 있는 source 변경은 workspace 내부 git commit으로 정리한 뒤 patch로 export하여 `bsp/*/patches/`에 저장한다.
  - 다른 머신에서는 동일 TI SDK와 `TI_BringUP` repo의 prepare/build script를 이용해 workspace를 재현한다.
- 영향:
  - `TI_BringUP` repo는 source mirror가 아니라 BSP 변경사항, 문서, manifest, script, patch, board note 저장소로 운영한다.
  - 장기 보관 대상은 source tree 전체가 아니라 patch, config fragment, DTS 후보, rootfs overlay, build/install script, manifest가 된다.
  - local AI Agent는 `workspace/`의 source tree를 참조해 코드 분석과 빌드를 수행할 수 있지만, 해당 source tree는 원격 repo에 push하지 않는다.
  - TI SDK 버전이 변경되면 새 SDK source tree에 기존 patch set을 재적용하여 호환성을 검증한다.
- 재검토 조건:
  - 실제 커스텀 보드 개발 과정에서 U-Boot/Linux core code 수정이 많아져 patch 관리만으로 추적이 어려워질 때
  - 여러 개발 머신 또는 협업자가 동일 source tree branch를 공유해야 할 필요가 생길 때
  - Yocto 기반 제품 이미지 관리 단계로 넘어가 `meta-nstel` 또는 custom BSP layer 중심 운영이 필요해질 때
  - TI SDK major version 변경으로 기존 patch set 재적용 비용이 커질 때