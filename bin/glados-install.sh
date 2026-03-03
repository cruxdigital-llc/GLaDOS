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
IS_UPGRADE="false"

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
    
    # 1. Check for LOCAL PROJECT overlay (Highest Priority)
    if [ -n "$OVERLAY" ]; then
        if [ -f "$TARGET_DIR/glados/overlays/$OVERLAY/$filename" ]; then
             source="$TARGET_DIR/glados/overlays/$OVERLAY/$filename"
             if [ "$VERBOSE" = "true" ]; then
                 echo "  (Local Overlay) Using $source"
             fi
        elif [ -f "$SRC_OVERLAYS/$OVERLAY/$filename" ]; then
            source="$SRC_OVERLAYS/$OVERLAY/$filename"
            if [ "$VERBOSE" = "true" ]; then
                 echo "  (Source Overlay) Using $source"
            fi
        fi
    fi

    # Ensure directory exists
    mkdir -p "$(dirname "$dest")"

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

    # 2. Resolve path placeholders based on install mode
    resolve_placeholders "$dest"
    
    if [ "$VERBOSE" = "true" ]; then
        echo "  Installed $filename to $dest"
    fi
}

# Remove legacy underscore-named files that have been replaced with dash-named equivalents.
# Scans the given directory for files containing underscores and removes them if a
# corresponding dash-named file exists.
cleanup_legacy_files() {
    local dir="$1"
    [ -d "$dir" ] || return

    for file in "$dir"/*_*.md; do
        [ -e "$file" ] || continue
        local dash_version
        dash_version="$(echo "$file" | tr '_' '-')"
        if [ -f "$dash_version" ]; then
            rm "$file"
            if [ "$VERBOSE" = "true" ]; then
                echo "  Cleaned up legacy file: $(basename "$file")"
            fi
        fi
    done
}

# Resolve {{PLACEHOLDER}} variables in an installed file based on MODE.
# Placeholders: {{STATUS}}, {{MODULES}}, {{PERSONAS}}, {{STANDARDS}}, {{SPECS}}
resolve_placeholders() {
    local file="$1"
    
    # Determine mode-specific paths
    local path_status path_modules path_personas
    case "$MODE" in
        antigravity)
            path_status="glados/PROJECT_STATUS.md"
            path_modules=".agent/modules"
            path_personas=".agent/personas"
            ;;
        claude)
            path_status="glados/PROJECT_STATUS.md"
            path_modules="glados/modules"
            path_personas="glados/personas"
            ;;
        gemini)
            path_status="glados/PROJECT_STATUS.md"
            path_modules="modules"
            path_personas="personas"
            ;;
        direct)
            path_status="glados/PROJECT_STATUS.md"
            path_modules="glados/modules"
            path_personas="glados/personas"
            ;;
    esac

    # Apply replacements (portable sed across macOS and Linux)
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' \
            -e "s|{{STATUS}}|${path_status}|g" \
            -e "s|{{MODULES}}|${path_modules}|g" \
            -e "s|{{PERSONAS}}|${path_personas}|g" \
            "$file"
    else
        sed -i \
            -e "s|{{STATUS}}|${path_status}|g" \
            -e "s|{{MODULES}}|${path_modules}|g" \
            -e "s|{{PERSONAS}}|${path_personas}|g" \
            "$file"
    fi
}

# -----------------------------------------------------------------------------
# Scaffolding
# -----------------------------------------------------------------------------

scaffold_glados() {
    local target="$1"
    if [ "$IS_UPGRADE" = "true" ]; then
        print_status "Updating GLaDOS structure in $target/glados..."
    else
        print_status "Scaffolding GLaDOS structure in $target/glados..."
    fi
    
    local glados_dir="$target/glados"
    mkdir -p "$glados_dir"
    mkdir -p "$glados_dir/personas"
    mkdir -p "$glados_dir/overlays"
    mkdir -p "$glados_dir/observations"
    mkdir -p "$glados_dir/philosophies"
    mkdir -p "$glados_dir/standards"
    
    # 1. PROJECT_STATUS.md
    if [ ! -f "$glados_dir/PROJECT_STATUS.md" ]; then
        if [ -f "$SRC_TEMPLATES/PROJECT_STATUS.md" ]; then
            cp "$SRC_TEMPLATES/PROJECT_STATUS.md" "$glados_dir/PROJECT_STATUS.md"
            print_status "Created $glados_dir/PROJECT_STATUS.md"
        fi
    else
        if [ "$VERBOSE" = "true" ]; then
            echo "  Skipping PROJECT_STATUS.md (already exists)"
        fi
    fi
    
    # 2. Personas (copy standard personas, updates propagate on reinstall)
    for file in "$SRC_PERSONAS"/*.md; do
        [ -e "$file" ] || continue
        cp "$file" "$glados_dir/personas/"
    done
    cleanup_legacy_files "$glados_dir/personas"
    
    # 3. Overlays README
    if [ ! -f "$glados_dir/overlays/README.md" ]; then
         if [ -f "$SRC_TEMPLATES/OVERLAYS_README.md" ]; then
            cp "$SRC_TEMPLATES/OVERLAYS_README.md" "$glados_dir/overlays/README.md"
         else
            echo "# GLaDOS Overlays" > "$glados_dir/overlays/README.md"
         fi
    fi

    # 4. Observations (staging area for pattern-observer)
    cleanup_legacy_files "$glados_dir/observations"
    if [ ! -f "$glados_dir/observations/observed-standards.md" ]; then
        if [ -f "$SRC_TEMPLATES/OBSERVED_STANDARDS.md" ]; then
            cp "$SRC_TEMPLATES/OBSERVED_STANDARDS.md" "$glados_dir/observations/observed-standards.md"
        fi
    fi
    if [ ! -f "$glados_dir/observations/observed-philosophies.md" ]; then
        if [ -f "$SRC_TEMPLATES/OBSERVED_PHILOSOPHIES.md" ]; then
            cp "$SRC_TEMPLATES/OBSERVED_PHILOSOPHIES.md" "$glados_dir/observations/observed-philosophies.md"
        fi
    fi

    # 5. Philosophies README
    if [ ! -f "$glados_dir/philosophies/README.md" ]; then
        if [ -f "$SRC_TEMPLATES/PHILOSOPHIES_README.md" ]; then
            cp "$SRC_TEMPLATES/PHILOSOPHIES_README.md" "$glados_dir/philosophies/README.md"
        fi
    fi

    # 6. Standards README
    if [ ! -f "$glados_dir/standards/README.md" ]; then
        if [ -f "$SRC_TEMPLATES/STANDARDS_README.md" ]; then
            cp "$SRC_TEMPLATES/STANDARDS_README.md" "$glados_dir/standards/README.md"
        fi
    fi
}

# -----------------------------------------------------------------------------
# Adapters
# -----------------------------------------------------------------------------

install_antigravity() {
    local target="$1/.agent/workflows"
    local action="Installing"
    [ "$IS_UPGRADE" = "true" ] && action="Upgrading"
    print_status "$action for Antigravity at $target..."
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
    
    # Install Personas
    # For Antigravity, we ALSO install to .agent/personas for internal tool use
    local persona_target="$1/.agent/personas"
    mkdir -p "$persona_target"
    for file in "$SRC_PERSONAS"/*.md; do
        [ -e "$file" ] || continue
        install_file "$file" "$persona_target/$(basename "$file")" "false"
    done

    # Clean up legacy underscore-named files
    cleanup_legacy_files "$target"
    cleanup_legacy_files "$1/.agent/modules"
    cleanup_legacy_files "$persona_target"
}

install_claude() {
    local target="$1/.claude/commands"
    local action="Installing"
    [ "$IS_UPGRADE" = "true" ] && action="Upgrading"
    print_status "$action for Claude at $target..."
    mkdir -p "$target"

    for file in "$SRC_WORKFLOWS"/*.md; do
        [ -e "$file" ] || continue
        install_file "$file" "$target/$(basename "$file")" "false"
    done

    # Clean up legacy underscore-named files
    cleanup_legacy_files "$target"
}

install_direct() {
    local target="$1/glados"
    local action="Installing"
    [ "$IS_UPGRADE" = "true" ] && action="Upgrading"
    print_status "$action directly to $target..."
    # Reuse scaffold logic somewhat, but direct needs specific subfolders for workflows
    mkdir -p "$target/workflows"
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

    # Clean up legacy underscore-named files
    cleanup_legacy_files "$target/workflows"
    cleanup_legacy_files "$target/modules"
}

install_gemini() {
    local target="$1/.gemini/skills/glados"
    local action="Installing"
    [ "$IS_UPGRADE" = "true" ] && action="Upgrading"
    print_status "$action for Gemini at $target..."
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

    # Install Workflows
    for file in "$SRC_WORKFLOWS"/*.md; do
        [ -e "$file" ] || continue
        dest="$target/workflows/$(basename "$file")"
        install_file "$file" "$dest" "false"
    done

    # Install Modules
    for file in "$SRC_MODULES"/*.md; do
        [ -e "$file" ] || continue
        dest="$target/modules/$(basename "$file")"
        install_file "$file" "$dest" "false"
    done

    # Install Personas
    for file in "$SRC_PERSONAS"/*.md; do
        [ -e "$file" ] || continue
        install_file "$file" "$target/personas/$(basename "$file")" "false"
    done

    # Clean up legacy underscore-named files
    cleanup_legacy_files "$target/workflows"
    cleanup_legacy_files "$target/modules"
    cleanup_legacy_files "$target/personas"
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

# Detect if this is an upgrade
if [ -d "$TARGET_DIR/glados" ]; then
    IS_UPGRADE="true"
    print_status "Existing GLaDOS installation detected — upgrading..."
else
    print_status "Installing GLaDOS..."
fi

# Always scaffold the glados directory regardless of mode
# EXCEPT for direct mode, which installs INTO glados/, so we be careful not to double up or conflict.
# But 'scaffold_glados' handles the extras (PROJECT_STATUS, personas, overlays dir).
# Direct mode function mainly handles workflows/modules.
scaffold_glados "$TARGET_DIR"

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

if [ "$IS_UPGRADE" = "true" ]; then
    print_status "Upgrade complete!"
else
    print_status "Installation complete!"
fi

