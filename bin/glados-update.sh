#!/bin/bash

# =============================================================================
# GLaDOS Update
# =============================================================================
# Refreshes the GLaDOS installation and optionally ingests local overlays.

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
SRC_Overlays="$ROOT_DIR/src/overlays"

TARGET_DIR=""
INGEST_OVERLAYS="false"
MODE="antigravity" # Default, or try to detect? 
# Detection is hard without state. Better to ask user or default to AG if uncertain.
# Or we can look for .agent/workflows .claude, etc.

detect_mode() {
    if [ -d "$TARGET_DIR/.agent/workflows" ]; then
        echo "antigravity"
    elif [ -d "$TARGET_DIR/.gemini/skills/glados" ]; then
        echo "gemini"
    elif [ -d "$TARGET_DIR/.claude/commands" ]; then
        echo "claude"
    elif [ -d "$TARGET_DIR/glados/workflows" ]; then
        echo "direct"
    else
        echo "unknown"
    fi
}

# Parse Args
while [[ $# -gt 0 ]]; do
    case $1 in
        --ingest-overlays)
            INGEST_OVERLAYS="true"
            shift
            ;;
        --target)
            TARGET_DIR="$2"
            shift 2
            ;;
         --mode)
            MODE="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [--ingest-overlays] [--target <dir>] [--mode <mode>]"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

if [ -z "$TARGET_DIR" ]; then
    TARGET_DIR="$(pwd)"
fi

if [ "$MODE" = "" ] || [ "$MODE" = "detect" ]; then
    MODE=$(detect_mode)
    if [ "$MODE" = "unknown" ]; then
        echo "Could not detect installation mode. Please specify --mode <antigravity|gemini|claude|direct>."
        exit 1
    fi
    echo "Detected mode: $MODE"
fi

echo "Updating GLaDOS in $TARGET_DIR (Mode: $MODE)..."

# Base install (refresh)
# Using 'antigravity' as default if we just detected it. 
# We re-run install script.

# If Ingest Overlays is ON, we find all directories in glados/overlays
# and run install for each one as an overlay.

if [ "$INGEST_OVERLAYS" = "true" ]; then
    if [ -d "$TARGET_DIR/glados/overlays" ]; then
        echo "Ingesting overlays from $TARGET_DIR/glados/overlays..."
        # Iterate over directories
        for overlay_dir in "$TARGET_DIR/glados/overlays"/*; do
            if [ -d "$overlay_dir" ]; then
                overlay_name=$(basename "$overlay_dir")
                echo "Applying overlay: $overlay_name"
                "$SCRIPT_DIR/glados-install.sh" --mode "$MODE" --target "$TARGET_DIR" --overlay "$overlay_name"
            fi
        done
    else
        echo "No overlays directory found at $TARGET_DIR/glados/overlays"
    fi
else
    # Just a standard refresh
    "$SCRIPT_DIR/glados-install.sh" --mode "$MODE" --target "$TARGET_DIR"
fi

echo "Update complete."
