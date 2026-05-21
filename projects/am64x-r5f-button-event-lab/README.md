# AM64x R5F Button Event Lab

This is the Phase 2 lab for SK-AM64B button-event bring-up. It is a standalone project derived from the Phase 1 project shape, but `projects/am64x-r5f-hw-control-lab` remains reference-only and is not part of this implementation.

Phase 2 verifies the reverse direction from Phase 1:

```text
SK-AM64B SW1 -> MCU_GPIO0_6 -> R5F GPIO interrupt -> RPMsg text event -> A53 r5ctl
```

Key properties:

- R5F project: `am64x_r5f_button_event_lab_r5fss0_0_freertos_ti_arm_clang`
- RPMsg service: `rpmsg_chrdev`
- RPMsg endpoint: `14`
- A53 binary: `r5ctl`
- Button input: `SW1` on `MCU_GPIO0_6`
- Active-low mapping: raw `0` is pressed/falling, raw `1` is released/rising
- Protocol: text only

## Layout

```text
projects/am64x-r5f-button-event-lab/
  a53/                 A53 Linux r5ctl source
  board/               board-side apply/restore/test script
  docs/                protocol, board apply, test, ownership, issues, completion notes
  r5f/                 R5F firmware, SysConfig, CCS projectspec
```

## Build

```bash
./tools/build/build-am64x-r5f-button-event-lab.sh r5f
./tools/build/build-am64x-r5f-button-event-lab.sh a53
./tools/build/build-am64x-r5f-button-event-lab.sh all
```

Build outputs are under `out/am64x-r5f-button-event-lab/` to avoid Phase 1 collisions.

## Deploy

```bash
./tools/install/deploy-am64x-r5f-button-event-lab-host.sh 192.168.0.110
# Optional one-step activation from host; this reboots the board.
./tools/install/deploy-am64x-r5f-button-event-lab-host.sh 192.168.0.110 apply
```

The deploy step copies firmware, `r5ctl`, and the board manage script. It does not runtime stop/start remoteproc by default.

On the board:

```bash
/usr/local/sbin/am64x-r5f-button-event-lab-manage.sh apply
/usr/local/sbin/am64x-r5f-button-event-lab-manage.sh test ping
/usr/local/sbin/am64x-r5f-button-event-lab-manage.sh test button status
/usr/local/sbin/am64x-r5f-button-event-lab-manage.sh test button wait 5000
/usr/local/bin/r5ctl button monitor
/usr/local/sbin/am64x-r5f-button-event-lab-manage.sh restore
```
