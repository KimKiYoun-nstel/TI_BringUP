# Qbu Project Closure Checklist

프로젝트 close는 아래 항목이 모두 완료됐을 때만 가능하다.

| 항목 | 현재 상태 | close 조건 |
|---|---|---|
| clean rootfs baseline | 관리 시작 | overlay script를 실제 deployment flow로 적용하고 reboot evidence 저장 |
| Qbu image delta | 없음 | custom kernel/DTB/rootfs image 변경 없이 runtime 설정만 사용 |
| TI SDK prebuilt certificate | 미취득 | prebuilt actual-Qbu claim이 필요할 때 `REPRODUCTION.md` 1회 실행 |
| canonical TMDS sender certificate | 증거 보유 | `REPRODUCTION.md` 절차를 hash-identified image에서 1회 재실행하고 raw evidence 저장 |
| counter acceptance rule | 관리됨 | sender/RX delta 및 error rule을 모든 certificate에 적용 |
| SK sender 100 Mbps certificate | 증거 보유 | 필요 시 clean baseline에서 raw evidence 재수집 |
| SK sender 1 Gbps | 미판정 | `CONFIG_NET_PKTGEN` 기반 overlap 시험 완료 또는 명시적 out-of-scope 결정 |
| Pair A verify-on asymmetry | 미해결 | out-of-scope 결정 또는 separate issue로 승격 |
| ICSSG sender | 미검증 | out-of-scope 결정 또는 별도 validation 수행 |

## 현재 결론

현재 repo는 Qbu의 결과 해석과 시험 절차를 관리한다. Qbu feature에는 custom image가 필요하지
않으며 clean rootfs baseline 위에서 runtime 설정으로 시험한다. historical raw evidence는
curated ledger로 보관돼 있으므로, stricter closeout을 원하면 canonical procedure의 raw evidence를
한 번 더 수집한다.

이 checklist를 완료하거나 각 미검증 항목을 명시적으로 out-of-scope로 승인한 뒤에만
프로젝트를 close한다.

새 kernel/DTB image는 Qbu feature enable에 필요하지 않다. TI SDK prebuilt image에서 actual-Qbu
counter certificate가 필요할 때만 해당 image로 재시험한다.
