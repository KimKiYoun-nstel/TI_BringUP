# CPU_Brd_V03_PBA Hardware Semantic DB v0.3

이 DB는 `CPU_Brd_V03_PBA_260511.pdf` 회로도에서 DTS 생성에 필요한 보드 의미를 추출한 2차 보강본이다.

## 목적

- `.NET + SysConfig` 기반 delivery DTS에서 누락된 회로도 의도를 보강한다.
- AI Agent가 매번 PDF를 다시 깊게 해석하지 않고, 검토된 hardware fact를 기준으로 Linux/U-Boot/SPL DTS를 생성하게 한다.
- 회로도 fact와 BSP policy를 분리해 DTS 생성 실수를 줄인다.

## 파일 구성

```text
00_db_schema.yaml
01_board_identity.yaml
02_memory_and_reserved.yaml
03_boot_media.yaml
04_power_tree.yaml
05_interfaces.yaml
06_reset_interrupt_gpio.yaml
07_clocking.yaml
08_fpga_semantics.yaml
09_vpx_connectors.yaml
10_dts_generation_policy.yaml
11_delivery_gap_report.md
12_unresolved_items.yaml
13_evidence_map.md
14_pdf_to_db_page_coverage.yaml
15_pdf_raw_text_by_page.md
16_pdf_to_db_fidelity_report.md
README.md
```

## v0.2에서 보강한 내용

- PMIC/TPS6522053 rail, address, control signal 상세화
- eMMC/OSPI의 hardware fact와 bring-up policy 분리
- OSPI octal wired fact와 single fallback policy 분리
- Ethernet PHY strap/address/reset/interrupt aggregation 정리
- USB/SERDES/PCIe channel switch 의미 정리
- GPMC-FPGA interface를 Linux enable 후보가 아니라 deferred policy 항목으로 분리
- FPGA Bank14/15/34/216의 DTS 영향도 정리
- VPX P0/P1/P2 connector mapping 초안 추가
- delivery DTS gap report 추가
- evidence map 추가

## 사용 규칙

1. `fact`는 회로도 근거로 사용한다.
2. `policy`는 사용자가 선택하거나 BSP 정책 문서가 있을 때만 DTS에 확정 반영한다.
3. `review_required: true`는 최종 DTS에서 확정하지 말고 TODO 또는 disabled로 남긴다.
4. DTS 생성 후 `11_delivery_gap_report.md`를 업데이트한다.

## 현재 한계

이 DB는 회로도 리뷰 완료 문서가 아니다. 특히 PMIC Linux binding, reset GPIO provider, interrupt aggregation, OSPI octal boot root cause, GPMC timing/register map, USB/SERDES mode는 별도 검토가 필요하다.

## v0.3 PDF-to-DB 1:1 Traceability 보강

이번 버전은 PDF 45 page 전체를 page-level로 DB에 대응시켰다. 핵심 추가 파일은 다음과 같다.

- `14_pdf_to_db_page_coverage.yaml`: 45/45 page coverage, DTS relevance, observable facts, PDF 외부 필요 정보 분리
- `15_pdf_raw_text_by_page.md`: PDF text layer를 page별로 보존
- `16_pdf_to_db_fidelity_report.md`: 100% coverage 기준과 한계 명시

주의: 여기서 100%는 PDF-to-DB traceability 기준이다. DTS 최종 확정률이나 hardware sign-off를 의미하지 않는다.
