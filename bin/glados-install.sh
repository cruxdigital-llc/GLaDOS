#!/bin/bash

# =============================================================================
# GLaDOS Installer
# =============================================================================

set -e

# -----------------------------------------------------------------------------
# Configuration & Defaults
# -----------------------------------------------------------------------------

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
SRC_WORKFLOWS="$ROOT_DIR/src/workflows"
SRC_MODULES="$ROOT_DIR/src/modules"
SRC_PERSONAS="$ROOT_DIR/src/personas"
SRC_TEMPLATES="$ROOT_DIR/src/templates"
SRC_OVERLAYS="$ROOT_DIR/src/overlays"

MODE=""
TARGET_DIR=""
OVERLAY=""
VERBOSE="false"

# -----------------------------------------------------------------------------
# Common Functions
# -----------------------------------------------------------------------------

print_status() {
    echo ">> $1"
}

print_error() {
    echo "ERROR: $1" >&2
}

show_help() {
    cat << EOF
Usage: $0 [OPTIONS]

Install GLaDOS workflows into your project.

Options:
    --mode <mode>       Installation mode: 'antigravity', 'claude', 'direct' (required)
    --target <path>     Target project directory (default: current directory)
    --overlay <name>    Apply a specific overlay from src/overlays/<name>
    --verbose           Show detailed output
    -h, --help          Show this help message

Modes:
    antigravity   Installs to .agent/workflows with YAML frontmatter
    claude        Installs to .claude/commands (standard markdown)
    gemini        Installs to .gemini/skills/glados (Agent Skills standard)
    direct        Installs to glados/ in the project root
EOF
    exit 0
}

# -----------------------------------------------------------------------------
# Installation Helpers
# -----------------------------------------------------------------------------

# Usage: install_file <source_path> <dest_path> [add_frontmatter]
install_file() {
    local source="$1"
    local dest="$2"
    local add_frontmatter="$3"
    
    local filename=$(basename "$source")
    
    # Check for overlay replacement
    if [ -n "$OVERLAY" ] && [ -f "$SRC_OVERLAYS/$OVERLAY/$filename" ]; then
        source="$SRC_OVERLAYS/$OVERLAY/$filename"
        if [ "$VERBOSE" = "true" ]; then
             echo "  (Overlay) Using $source"
        fi
    fi

    if [ "$add_frontmatter" = "true" ]; then
        # Extract title from the first line (assuming # Title format)
        title=$(head -n 1 "$source" | sed 's/^# //')
        
        echo "---" > "$dest"
        echo "description: $title" >> "$dest"
        echo "---" >> "$dest"
        echo "" >> "$dest"
        cat "$source" >> "$dest"
    else
        cp "$source" "$dest"
    fi
    
    if [ "$VERBOSE" = "true" ]; then
        echo "  Installed $filename to $dest"
    fi
}

# -----------------------------------------------------------------------------
# Adapters
# -----------------------------------------------------------------------------

install_antigravity() {
    local target="$1/.agent/workflows"
    print_status "Installing for Antigravity at $target..."
    mkdir -p "$target"

    # Install Workflows
    for file in "$SRC_WORKFLOWS"/*.md; do
        [ -e "$file" ] || continue
        install_file "$file" "$target/$(basename "$file")" "true"
    done
    
    # Install Templates (hidden)
    mkdir -p "$1/.agent/templates"
    cp "$SRC_TEMPLATES"/*.md "$1/.agent/templates/" 2>/dev/null || true

    # Install Modules (hidden/support)
    mkdir -p "$1/.agent/modules"
    for file in "$SRC_MODULES"/*.md; do
        [ -e "$file" ] || continue
        install_file "$file" "$1/.agent/modules/$(basename "$file")" "false"
    done
    
    # Install Personas (hidden or visible? For AG, maybe visible workflows?)
    # For now, let's put them in .agent/personas
    local persona_target="$1/.agent/personas"
    mkdir -p "$persona_target"
    for file in "$SRC_PERSONAS"/*.md; do
        [ -e "$file" ] || continue
        install_file "$file" "$persona_target/$(basename "$file")" "false"
    done
}

install_claude() {
    local target="$1/.claude/commands"
    print_status "Installing for Claude at $target..."
    mkdir -p "$target"

    for file in "$SRC_WORKFLOWS"/*.md; do
        [ -e "$file" ] || continue
        install_file "$file" "$target/$(basename "$file")" "false"
    done
    
    # Claude doesn't inherently support a persona directory structure in commands
    # We might leave them as reference files
}

install_direct() {
    local target="$1/glados"
    print_status "Installing directly to $target..."
    mkdir -p "$target"
    mkdir -p "$target/workflows"
    mkdir -p "$target/templates"
    mkdir -p "$target/personas"
    mkdir -p "$target/modules"

    # Workflows
    for file in "$SRC_WORKFLOWS"/*.md; do
        [ -e "$file" ] || continue
        install_file "$file" "$target/workflows/$(basename "$file")" "false"
    done
    
    # Modules
    for file in "$SRC_MODULES"/*.md; do
        [ -e "$file" ] || continue
        install_file "$file" "$target/modules/$(basename "$file")" "false"
    done
    
    # Templates
    cp "$SRC_TEMPLATES"/*.md "$target/templates/" 2>/dev/null || true
    
    # Personas
    for file in "$SRC_PERSONAS"/*.md; do
        [ -e "$file" ] || continue
        install_file "$file" "$target/personas/$(basename "$file")" "false"
    done
    
    # Create a simple README in the target
    echo "# GLaDOS Workflows" > "$target/README.md"
    echo "Run these workflows directly or use them as reference." >> "$target/README.md"
}

install_gemini() {
    local target="$1/.gemini/skills/glados"
    print_status "Installing for Gemini at $target..."
    mkdir -p "$target"
    mkdir -p "$target/workflows"
    mkdir -p "$target/modules"
    mkdir -p "$target/personas"

    # Install SKILL.md
    if [ -f "$SRC_TEMPLATES/SKILL_GEMINI.md" ]; then
        cp "$SRC_TEMPLATES/SKILL_GEMINI.md" "$target/SKILL.md"
    else
        echo "WARNING: SKILL_GEMINI.md not found in templates."
    fi

    # Install Workflows (with path adaptation)
    for file in "$SRC_WORKFLOWS"/*.md; do
        [ -e "$file" ] || continue
        dest="$target/workflows/$(basename "$file")"
        install_file "$file" "$dest" "false"
        
        # Adaptation: Gemini skill files are typically relative or looked up by name.
        # We replace specific "glados/" path prefixes to generic relative ones so the agent looks in the skill bundle.
        if [[ "$OSTYPE" == "darwin"* ]]; then
            sed -i '' 's|glados/modules/|modules/|g' "$dest"
            sed -i '' 's|glados/personas/|personas/|g' "$dest"
        else
            sed -i 's|glados/modules/|modules/|g' "$dest"
            sed -i 's|glados/personas/|personas/|g' "$dest"
        fi
    done

    # Install Modules
    for file in "$SRC_MODULES"/*.md; do
        [ -e "$file" ] || continue
        dest="$target/modules/$(basename "$file")"
        install_file "$file" "$dest" "false"
        # Adapt self-references if any
        if [[ "$OSTYPE" == "darwin"* ]]; then
            sed -i '' 's|glados/personas/|personas/|g' "$dest"
        else
            sed -i 's|glados/personas/|personas/|g' "$dest"
        fi
    done

    # Install Personas
    for file in "$SRC_PERSONAS"/*.md; do
        [ -e "$file" ] || continue
        install_file "$file" "$target/personas/$(basename "$file")" "false"
    done
}

# -----------------------------------------------------------------------------
# Main Logic
# -----------------------------------------------------------------------------

if [ $# -eq 0 ]; then
    show_help
fi

while [[ $# -gt 0 ]]; do
    case $1 in
        --mode)
            MODE="$2"
            shift 2
            ;;
        --target)
            TARGET_DIR="$2"
            shift 2
            ;;
        --overlay)
            OVERLAY="$2"
            shift 2
            ;;
        --verbose)
            VERBOSE="true"
            shift
            ;;
        -h|--help)
            show_help
            ;;
        *)
            print_error "Unknown option: $1"
            show_help
            ;;
    esac
done

if [ -z "$MODE" ]; then
    print_error "Mode is required (--mode)"
    show_help
fi

if [ -z "$TARGET_DIR" ]; then
    TARGET_DIR="$(pwd)"
fi

if [ ! -d "$TARGET_DIR" ]; then
    print_error "Target directory does not exist: $TARGET_DIR"
    exit 1
fi

case "$MODE" in
    antigravity)
        install_antigravity "$TARGET_DIR"
        ;;
    claude)
        install_claude "$TARGET_DIR"
        ;;
    gemini)
        install_gemini "$TARGET_DIR"
        ;;
    direct)
        install_direct "$TARGET_DIR"
        ;;
    *)
        print_error "Invalid mode: $MODE"
        show_help
        ;;
esac

print_status "Installation complete!"
