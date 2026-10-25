#!/usr/bin/env bash
set -euo pipefail

# install-skill.sh: Install the oss-steward maintainer skill across agent platforms.
#
# Usage:
#   bash scripts/install-skill.sh [TARGET] [OPTIONS]
#
# Targets:
#   workspace (default) - Installs into .agents/skills/oss-steward
#   global              - Installs into ~/.gemini/antigravity-cli/skills and ~/.agents/skills
#   claude              - Installs into .claude/skills/oss-steward
#   cursor              - Installs .cursor/rules/oss-steward.mdc
#   all                 - Installs across workspace, claude, and cursor
#   custom <path>       - Installs to an explicit directory

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Try using gh-beads skill CLI if uv is available
if command -v uv >/dev/null 2>&1 && [ -f "$REPO_ROOT/pyproject.toml" ]; then
    exec uv run --project "$REPO_ROOT" --locked gh-beads skill install "$@"
fi

# Fallback: pure shell copying
TARGET="${1:-workspace}"
DEST_BASE="${2:-.}"
SKILL_SRC="$REPO_ROOT/skills/oss-steward"

if [ ! -d "$SKILL_SRC" ]; then
    echo "Error: Skill source not found at $SKILL_SRC" >&2
    exit 1
fi

case "$TARGET" in
    workspace|agents)
        DEST="$DEST_BASE/.agents/skills/oss-steward"
        mkdir -p "$DEST"
        cp -r "$SKILL_SRC"/* "$DEST/"
        echo "✓ Installed oss-steward skill to $DEST"
        ;;
    global)
        for G_DEST in "$HOME/.gemini/antigravity-cli/skills/oss-steward" "$HOME/.agents/skills/oss-steward"; do
            mkdir -p "$G_DEST" 2>/dev/null || true
            if [ -d "$G_DEST" ]; then
                cp -r "$SKILL_SRC"/* "$G_DEST/" 2>/dev/null || true
                echo "✓ Installed oss-steward skill to $G_DEST"
            fi
        done
        ;;
    claude)
        DEST="$DEST_BASE/.claude/skills/oss-steward"
        mkdir -p "$DEST"
        cp -r "$SKILL_SRC"/* "$DEST/"
        echo "✓ Installed oss-steward skill to $DEST"
        ;;
    *)
        echo "Usage: bash scripts/install-skill.sh [workspace|global|claude|all] [DEST_DIR]" >&2
        exit 1
        ;;
esac
