# PDF-to-DB Fidelity Report v0.3

## 목적

이 버전의 목표는 `CPU_Brd_V03_PBA_260511.pdf`의 DTS 활용 목적 정보가 DB에서 누락되지 않도록 page-level 1:1 traceability를 만드는 것이다. 사용자 요청에 따라 OrCAD `.NET`에 표현되는 순수 연결 정보는 이 fidelity 판단 범위에서 제외한다.

## 100%로 맞춘 기준

- PDF 45 page 전체가 `14_pdf_to_db_page_coverage.yaml`에 1:1로 존재한다.
- 각 page는 DTS relevance가 `dts_relevant`, `indirect_or_supporting`, `not_dts_relevant_blank` 중 하나로 분류된다.
- 각 page의 DTS 관련 observable fact는 `observable_facts_for_dts`로 전사된다.
- PDF에 없어서 결정할 수 없는 항목은 `external_information_not_in_pdf`로 분리한다.
- 추출 가능한 PDF text layer는 `15_pdf_raw_text_by_page.md`에 page별로 보존한다.

## Coverage 결과

| 항목 | 결과 |
|---|---:|
| PDF 총 page | 45 |
| DB coverage page | 45 |
| Page coverage | 100% |
| DTS relevance classified | 45/45 |
| Unclassified page | 0 |

## 중요한 해석

이 `100%`는 hardware sign-off나 Linux DTS 최종 확정률이 아니다. 여기서의 100%는 PDF-to-DB 변환 추적성 기준이다. 즉 PDF에 있는 DTS 목적의 정보는 DB 안에서 page별로 찾을 수 있고, PDF에 없는 정보는 별도로 표시된다.

## PDF 자체에 없어서 DB가 확정할 수 없는 대표 항목

- reserved-memory 최종 layout
- OP-TEE/R5F carveout 사용 정책
- OSPI partition layout
- Boot ROM octal failure root cause
- U-Boot env 위치
- Linux kernel/rootfs 저장 위치
- GPMC-FPGA register map/timing/window
- USB vs PCIe final SerDes product mode
- Linux kernel binding compatible string 검증

## PDF에는 있지만 .NET cross-check가 필요한 항목

- GPIO provider와 실제 GPIO 번호
- reset/interrupt provider path
- FPGA-mediated control signal의 Linux visible 여부
- DNI/NC 부품에 따른 최종 assembly 경로

## 다음 사용법

DTS Agent는 먼저 `14_pdf_to_db_page_coverage.yaml`을 읽어 page별 fact를 확인하고, 기존 semantic YAML 파일에서 구체 node 후보를 찾는다. 어떤 항목이 `external_information_not_in_pdf`에 있으면 PDF 재분석으로 해결하려고 하지 말고 정책/커널 binding/boot log/.NET cross-check 단계로 넘긴다.
