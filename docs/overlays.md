# Overlays

Overlays allow you to customize GLaDOS without forking the entire repository.

## How it Works

1.  Create a directory matching your overlay name: `src/overlays/my-custom-setup/`.
2.  Place modified versions of any file (workflow, module, or persona) in that directory.
    -   *Example*: To change how features are planned, copy `src/workflows/plan-feature.md` to `src/overlays/my-custom-setup/plan-feature.md` and edit it.
3.  Install with the overlay flag:
    ```bash
    ./bin/glados-install.sh --mode <mode> --overlay my-custom-setup
    ```

The installer will prefer files found in the overlay directory over the defaults in `src/`.
