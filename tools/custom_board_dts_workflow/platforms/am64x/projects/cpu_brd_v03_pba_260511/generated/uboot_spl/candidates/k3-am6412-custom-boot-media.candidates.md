# Boot Media Candidates

이 파일은 hardware facts와 기본 규칙을 기준으로 U-Boot/SPL boot media 후보를 기록한다.

## MMC0
- detected: yes
- controller_ready_from_facts: yes
- readiness_rule: CLK/CMD/DAT0 required

## OSPI0
- detected: yes
- controller_ready_from_facts: yes
- readiness_rule: CLK/CSN0/D0 required
