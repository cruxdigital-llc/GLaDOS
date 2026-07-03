# GLaDOS Overlays

Overlay ingestion was a **v1** installer feature (`glados-update.sh
--ingest-overlays`), and those scripts are retired; the v2 compiler does not
read this directory.

To customize GLaDOS in v2:

- edit lane-2 keys in `glados.yaml` (channels, decisions, params, the persona
  roster) — live, no reinstall;
- drop project personas in `product-knowledge/personas/` (searched before the
  vendored `.glados/personas/` library);
- keep project standards and philosophies under `product-knowledge/`.

A structural change to workflow text means editing the GLaDOS source and
re-running `python bin/glados.py install`.
