# 2026-07-07 TMDS64EVM SD bootloader restore from backup

## 목적

TSN C Case cleanup의 일부로,
TMDS64EVM SD boot partition에 남아 있던 C Case lineage bootloader 3종을
pre-C-Case backup set으로 복원한 사실을 기록한다.

## 대상 partition

```text
/run/media/boot-mmcblk1p1
```

## 복원 전 active file hash

```text
tiboot3.bin  2f706e27f92ee178c081e0902e40aca00a08f72d230aad0399153889ec8d3c49
tispl.bin    1831deb785c7178329fe091742228f9de57d9b3ef040482cd2a4552813763bce
u-boot.img   262e8371723a469dd3a26d1567bb534145cd1bc7fab91aa7c75114e66908fd3a
```

위 hash는 host의 C Case build artifact와 일치했다.

```text
out/u-boot/artifacts/tiboot3.bin
out/u-boot/artifacts/tispl.bin
out/u-boot/artifacts/u-boot.img
```

## 복원 source

```text
/run/media/boot-mmcblk1p1/backup/bootloader/20260702_134807/
```

복원 source hash:

```text
tiboot3.bin  323e4e949138d6ec167319bc0292b91cc964e63fe854957727611179c6589f6c
tispl.bin    3bc0c14f354d53d803d2871999e95b194c1ac5a88c3592cfaf9fd84f57202c25
u-boot.img   eb1498a093a62f9450da4d6ab841106112b690c5248516a4b81c504c9f80e6dd
```

## safety backup

복원 직전 active set은 아래 경로에 재백업했다.

```text
/run/media/boot-mmcblk1p1/backup/bootloader/20260707_cleanup_pre_restore/
```

## 복원 후 검증

1. active file hash가 backup source hash와 일치함을 확인했다.
2. TMDS64EVM를 reboot했다.
3. UART 기준 `login:`까지 정상 복귀를 확인했다.
4. reboot 후 Linux shell에서 아래를 확인했다.

```text
78000000.r5f state=running
78000000.r5f firmware=am64-main-r5f0_0-fw
```

## 해석

- runtime firmware는 이미 default로 복귀해 있었지만,
  boot partition active bootloader 3종은 cleanup 전까지 C Case lineage 그대로 남아 있었다.
- 이번 복원으로 TMDS64EVM SD boot media 기준 C Case bootloader residue는 제거했다.
