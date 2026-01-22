# GLaDOS Overlays

This directory allow you to safely customize GLaDOS workflows, modules, and personas without modifying the core library.

## How to use

1.  Create a subdirectory for your overlay (e.g., `my-custom-overlay/`).
2.  Copy any file from the installed GLaDOS source (workflows, modules, personas) into this directory.
3.  Modify the file as needed.
4.  Run the update command to apply your changes:

```bash
./bin/glados-update.sh --ingest-overlays
```

## Structure

```
glados/
  overlays/
    README.md
    my-team-standards/        <-- Your overlay name
      plan_feature.md         <-- Overrides default plan_feature
      architect.md            <-- Overrides default architect persona
```
