# 2026-06-04 Phase2 Local Image Generation

## 목적

이 문서는 Phase2에서 board interaction 없이
local host 상에서 생성된 early-boot 관련 image artifact를 기록한다.

중요:

- local image generation provenance 이다.
- OSPI flash 또는 UART boot 성공을 의미하지 않는다.

## 실행 항목

### 1. R5F multicore ELF/appimage 후보

명령:

```bash
./tools/build/gen-r5f-multicore-appimage.sh --execute
```

결과:

- `out/sk-am64b-r5f-early-boot/images/r5f-early-heartbeat.mcelf`
- `out/sk-am64b-r5f-early-boot/images/r5f-early-heartbeat.mcelf.hs_fs`

### 2. Linux appimage 후보

명령:

```bash
./tools/build/gen-linux-appimage-for-sbl.sh --execute
```

결과:

- `out/r5f-early-boot/linux-appimage-build/linux.mcelf.hs_fs`
- `out/r5f-early-boot/linux-appimage-build/u-boot.img`

## 현재 확인된 artifact

| 항목 | 경로 |
|---|---|
| R5F MCELF | `out/sk-am64b-r5f-early-boot/images/r5f-early-heartbeat.mcelf` |
| R5F MCELF HS-FS | `out/sk-am64b-r5f-early-boot/images/r5f-early-heartbeat.mcelf.hs_fs` |
| Linux MCELF HS-FS | `out/r5f-early-boot/linux-appimage-build/linux.mcelf.hs_fs` |
| staged `u-boot.img` copy | `out/r5f-early-boot/linux-appimage-build/u-boot.img` |

## 해석

현재 Phase2는 다음 상태까지 도달했다.

```text
heartbeat local buildable draft: yes
R5F image generation path: yes
Linux image generation path: yes
board/UART verification: no
```

즉 repo/local host 기준으로는
Phase2의 non-destructive artifact preparation 축이 거의 완료되었다.

## 남은 경계

이후 Phase2를 최종 닫기 위해 필요한 것은 다음이다.

- 실제 OSPI artifact set 확정
- UART 기준 `SBL -> R5F -> Linux` 흐름 관찰
- Linux boot 이후 heartbeat 유지 여부 확인
