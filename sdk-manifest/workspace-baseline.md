# Workspace Baseline

Generated: 2026-05-13T14:40:00+09:00

The local BSP source workspaces were reset to clean Git HEADs and tagged as the SDK 12 baseline.

## Policy

- SDK source directories under `~/ti/am64x/.../board-support/` are reference inputs only.
- `TI_Bringup/workspace/` contains clean local working copies for analysis, patches, and builds.
- Existing dirty files from earlier SDK build tests were intentionally ignored and not preserved in the workspace baseline.
- Baseline tags are local to each workspace source Git repository.

## U-Boot Workspace

```text
Path: workspace/ti-u-boot-sdk12
Tag: ti-sdk-12.00.00.07.04-baseline
HEAD: 2549829cc194ffd9e38b755d2e10c7fc4cd971eb
```

## Linux Kernel Workspace

```text
Path: workspace/ti-linux-kernel-sdk12
Tag: ti-sdk-12.00.00.07.04-baseline
HEAD: c214492085504176b9c252a7175e4e60b4b442af
```

## Restore Commands

```bash
cd ~/ti/TI_Bringup/workspace/ti-u-boot-sdk12
git switch --detach ti-sdk-12.00.00.07.04-baseline

cd ~/ti/TI_Bringup/workspace/ti-linux-kernel-sdk12
git switch --detach ti-sdk-12.00.00.07.04-baseline
```
