# RootFS Overlay

Store only rootfs overlay files, service definitions, configuration snippets, and installation notes here.

Do not store a full unpacked root filesystem in this repo.

## Layout

```text
rootfs/
  overlay/                     shared overlay files already validated in the repo
  overlays/
    sk-am64b-lab-r5f/         profile-specific overlay for lab-only service policy
```

`overlay/` is for shared or already-adopted overlay content.

`overlays/<profile>/` is for explicit policy profiles that should remain separable from the shared baseline. For example, `sk-am64b-lab-r5f/` contains a lab marker and systemd drop-ins used to keep TI baseline RPMsg services installed but skipped at boot during lab firmware validation.
