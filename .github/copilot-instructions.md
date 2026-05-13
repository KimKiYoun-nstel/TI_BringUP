# Repository Instructions for AI Coding Agents

This repository is the active TI AM64x Embedded Linux BSP and board bring-up work repository.

It started as a documentation-oriented knowledge repository, but now also manages the local BSP development workflow around TI Processor SDK Linux AM64x 12.00.00.07.04.

Before making changes:

- Treat `PROJECT_BRIEF.md` as the project source of truth.
- Read `AI_AGENT_GUIDE.md` before changing code, scripts, patches, or docs.
- Check `sdk-manifest/workspace-baseline.md` and `sdk-manifest/source-commits.md` for baseline commits.
- Do not commit the full TI SDK source tree.
- Do not commit `workspace/`; it is local-only and ignored by parent Git.

Workspace policy:

- Use `workspace/ti-u-boot-sdk12` for U-Boot source analysis and edits.
- Use `workspace/ti-linux-kernel-sdk12` for Linux kernel source analysis and edits.
- Treat SDK source directories under `~/ti/am64x/.../board-support/` as references only.
- Preserve meaningful workspace changes as `git format-patch` output under `bsp/u-boot/patches/` or `bsp/linux/patches/`.
- Store configs, DTS candidates, rootfs overlay, scripts, logs, and docs in this parent repo.

Documentation policy:

- Keep board-specific notes under `docs/boards/<board-name>/` or `board/<board-name>/` depending on whether the note is long-term documentation or active working notes.
- Keep common AM64x knowledge under `docs/common/`.
- Record accepted decisions in `docs/decisions/DECISION_LOG.md`.
- Record reusable research notes in `docs/research/RESEARCH_NOTES.md`.
- Update `docs/tasks/TASK_BOARD.md` when task status changes.
- Do not present guesses as facts. Mark uncertain items as `확인 필요`.

Bring-up response style:

- Classify issues by boot stage: Boot ROM, SPL, U-Boot, kernel Image/DTB load, kernel boot, rootfs mount, services, peripheral validation.
- Prefer practical structure: what to check, files to modify, build/flash steps, log points, failure suspects.
- If workspace or SDK source has unexpected dirty changes, stop and ask before resetting or cleaning.
