# 2026-06-12 SK-AM64B SBL OSPI Linux LPDDR4 Dual-Boot Success

## 목적

이 문서는 SK-AM64B `SBL OSPI Linux` 작업에서
LPDDR4 기반 `dual-boot` 기본 경로로 다시 올라온 시점을 짧게 정리한다.

## 이번 세션 결론

```text
LPDDR4 reginit를 유지한 상태에서 원본 sbl_ospi_linux 기본 dual-boot 경로로 복귀했고,
U-Boot tftp + sf write 후 다시 Linux boot까지 성공했다.
```

## 이번 세션에서 확인한 것

1. `sbl_ospi_linux` 기본 경로에서 `App_loadImages`가 다시 성공했다.
2. `0x80000` R5F multicore appimage slot을 다시 사용했다.
3. `0x300000` `u-boot.img`, `0x800000` `linux.mcelf.hs_fs` write/readback CRC가 일치했다.
4. Linux boot 후 `remoteproc1/2 = attached`, `remoteproc3/4 = now up`가 관찰되었다.
5. 이후 workspace 정리에서 temporary debug marker/diag를 제거하고 clean source delta만 남기기로 했다.

## 이번 세션이 닫는 범위

- LPDDR4 reginit가 dual-boot 경로에서도 유지 가능한지
- OSPI layout `0x0 / 0x80000 / 0x300000 / 0x800000`로 다시 boot 가능한지
- early-boot 작업의 우선 closure를 `dual-boot`까지 둘 수 있는지

## 이번 세션이 아직 닫지 않는 범위

- custom early-boot R5F firmware가 의도한 SHM heartbeat를 실제 publish 하는지
- Linux baseline `rpmsg_json` app과 RPMsg round-trip이 바로 성립하는지

즉 현재 상태는:

```text
early-boot boot-chain closure: yes
R5F firmware/application behavior closure: no
```
