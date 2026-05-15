# 2026-05-14 SK-AM64B 부트 플로우 BASE 및 파이프라인 상태

## Knowledge

- 현재 동작 중인 SK-AM64B 부트 경로는 주로 U-Boot environment 변수에 의해 결정된다.
- 현재 보드는 Linux의 1차 boot policy로 `extlinux.conf`를 사용하지 않는다.
- 실제 Linux load 경로는 `/boot/Image`와 `/boot/dtb/ti/k3-am642-sk.dtb`이다.
- U-Boot가 Linux 시작 전 최종 runtime FDT를 수정할 수 있다.
- OSPI Flash는 SD 실험이 깨졌을 때 복구 기준점으로 운영할 수 있다.

## Evidence

### self-built U-Boot 부트 로그 기준

관찰된 순서:

```text
Loaded env from uEnv.txt
Importing environment from mmc1 ...
... kernel Image read ...
... DTB read ...
Booting using the fdt blob ...
Starting kernel ...
```

### U-Boot environment dump 기준

관찰된 값:

```text
bootcmd=run envboot; run bootcmd_ti_mmc; bootflow scan -lb
bootpart=1:2
bootdir=/boot
fdtfile=ti/k3-am642-sk.dtb
get_fdt_mmc=load mmc ${bootpart} ${fdtaddr} ${bootdir}/dtb/${fdtfile}
get_kern_mmc=load mmc ${bootpart} ${loadaddr} ${bootdir}/${name_kern}
run_kern=booti ${loadaddr} ${rd_spec} ${fdtaddr}
```

### 실보드 점검 기준

관찰된 runtime 값:

```text
console=ttyS2,115200n8
root=PARTUUID=076c4a2a-02
model=Texas Instruments AM642 SK
compatible=ti,am642-sk / ti,am642
```

관찰된 rootfs boot 자산:

```text
/boot/Image
/boot/dtb/ti/k3-am642-sk.dtb
```

관찰된 FAT boot 자산에는 bootloader 파일과 helper 파일이 있었지만, active `extlinux.conf` 기반 Linux 부팅은 확인되지 않았다.

## Decision

현재 U-Boot environment 기반 SD boot path를 파이프라인 BASE로 사용한다.

이 BASE를 quick-guide 시작점으로 보는 이유는 다음과 같다.

- TI prebuilt SD card layout을 반영한다.
- 현재 동작 중인 보드 상태와 일치한다.
- U-Boot 정책과 Linux runtime 상태를 직접 관찰한 결과다.

## Assumption

현재 SK-AM64B의 baseline Linux DTB는 다음 경로에서 로드되는 `k3-am642-sk.dtb`이다.

```text
/boot/dtb/ti/k3-am642-sk.dtb
```

## Open Question

- 향후 test/golden slot 관리가 꼭 필요해지면 extlinux로 갈지, direct U-Boot env boot를 유지할지?
- on-disk DTB와 runtime DT 사이에서 U-Boot가 정확히 어떤 FDT fixup을 적용하는지?

## Action Item

- baseline boot flow 및 Option A deploy 전략 문서화
- 현재 FAT boot partition 기준 bootloader deploy script 구현
- 현재 `/boot` 및 `/boot/dtb/ti/` 기준 kernel/DTB deploy script 구현
- 앞으로의 변경 이력은 모두 이 baseline 대비 delta로 기록
- OSPI write / recovery / boot mode switch 운용 기준 문서화

## Board Note

현재 보드는 `root@192.168.0.110` SSH 접속이 가능하므로 첫 deploy loop의 기준 보드로 사용 가능하다.

## Artifact

- baseline boot-flow 문서 추가
- Option A deploy 전략 확정
- bootloader / kernel build artifact 생성 스크립트 확보
- OSPI recovery를 deploy 전략에 포함해야 한다는 운영 요구 확인

## Follow-up Result

- 2026-05-15 기준으로 kernel+DTB deploy 후 reboot 및 SSH 복귀가 실제로 검증되었다.
- 이 결과는 첫 파이프라인 기반 kernel+DTB build/deploy/boot 성공 기록으로 별도 정리했다.
- 새 kernel image는 기존 TI prebuilt 계열 image보다 크며, 현재 파이프라인이 `make defconfig` 기반 generic kernel 구성을 사용하고 있음을 재확인했다.
- DTB-only 실제 deploy 및 reboot도 성공적으로 검증되었다.
- SD golden 세트와 U-Boot/TFTP recovery command template 문서가 추가되었다.
- U-Boot 단계에서 Host PC TFTP root의 golden kernel/DTB를 RAM으로 받아 부팅하는 recovery 경로도 실증되었다.

## Golden Baseline Result

- 현재 보드에 배포되어 정상 부팅이 검증된 repo-build kernel/DTB 세트가 golden 기준으로 승격되었다.
- 현재 golden 경로는 다음과 같다.

```text
/boot/Image.golden
/boot/dtb/ti/k3-am642-sk.dtb.golden
```

- 이 golden 세트는 이후 kernel+DTB 또는 DTB-only 실험에서 1차 복구 기준으로 사용한다.

## Current Pipeline Status

현재까지 실제 검증이 끝난 파이프라인 범위:

```text
Stage A  환경/경로 검증          완료
Stage B  bootloader build         완료
Stage C  bootloader deploy        완료
Stage D  kernel+DTB build         완료
Stage E  kernel+DTB deploy        완료
```

아직 남아 있는 범위:

```text
DTB-only 실제 deploy 검증
RootFS overlay build/deploy skeleton 및 실제 검증
TI prebuilt kernel config flow 확인
```
