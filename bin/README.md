# Binaries

This directory contains the executable scripts for GLaDOS.

## Scripts

### `glados-install.sh`
The core installer for the framework. It handles:
-   **Environment Detection**: Checks for existing configuration directories.
-   **Mode Selection**: Installs for `antigravity`, `claude`, or `direct` usage.
-   **Overlay Application**: Merges local customizations from `src/overlays/`.
-   **Module Injection**: Ensures `src/modules/` and `src/personas/` are correctly placed.

**Usage**:
```bash
./glados-install.sh --mode <mode> [--target <dir>] [--overlay <name>]
```
