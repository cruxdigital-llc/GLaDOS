# Overlays

Overlays were the **v1** mechanism for customizing GLaDOS without forking:
files placed under `src/overlays/<name>/` overrode same-named files in `src/`,
applied by the retired `glados-install.sh --overlay` flag.

**The v2 compiler (`bin/glados.py`) does not read overlay directories.** The
supported v2 customization surface is:

- **Lane-2 manifest keys** in `glados.yaml` — channels, merge authority,
  decisions, params, the persona roster. Edit and the next run behaves
  differently; no reinstall.
- **Project personas** in `product-knowledge/personas/` — searched before the
  library vendored into `.glados/personas/`, so a project file of the same
  name wins.
- **Project standards and philosophies** under `product-knowledge/` — read by
  the standards gate and review panels at run time.

A structural change to a core's text still means editing the source (in a
fork or checkout) and re-running `python bin/glados.py install --mode <mode>
--target /path/to/your/project`.
