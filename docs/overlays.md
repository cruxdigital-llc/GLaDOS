# Overlays

> Reference page, mostly for v1 users. New v2 terms below (*manifest*,
> *lanes*, *personas*) are defined in [concepts.md](concepts.md); the
> full v1-to-v2 procedure is [MIGRATION.md](../MIGRATION.md).

Overlays were the **v1** mechanism for customizing GLaDOS without forking:
files placed under `src/overlays/<name>/` overrode same-named files in `src/`,
applied by the retired `glados-install.sh --overlay` flag.

**The v2 compiler (`bin/glados.py`) does not read overlay directories.** The
supported v2 customization surface is:

- **Lane-2 manifest keys** in `glados.yaml` — channels, merge authority,
  decisions, params, the persona roster. Edit and the next run behaves
  differently; no reinstall.
- **Declared sinks** under `sinks:` in `glados.yaml` — add a destination the
  library never shipped (e.g. `slack`) and give it freeform config
  (`channel:`, `grouping:`, `threads:`, …) the agent interprets at run time.
  This is the v2 answer to "customize where and how results are delivered"
  without touching workflow text; see [guides/sinks.md](guides/sinks.md).
- **Project personas** in `product-knowledge/personas/` — searched before the
  library vendored into `.glados/personas/`, so a project file of the same
  name wins.
- **Project standards and philosophies** under `product-knowledge/` — read by
  the standards gate and review panels at run time.

A structural change to a core's text still means editing the source (in a
fork or checkout) and re-running `python bin/glados.py install --mode <mode>
--target /path/to/your/project`.
