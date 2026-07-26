#!/usr/bin/env bash
# Apply a Legion subagent DAG preset without disturbing unrelated config.

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

usage() {
    cat <<'EOF'
Usage: switch-subagents.sh [PRESET|list]

Apply PRESET from $GROK_HOME/config-presets (default: ~/.grok/config-presets),
or list installed presets and the active role mapping.

Examples:
  switch-subagents.sh list
  switch-subagents.sh legion-dag
  switch-subagents.sh auto-discovered
EOF
}

case "${1:-list}" in
    -h|--help|help)
        usage
        exit 0
        ;;
esac

exec python3 "$SCRIPT_DIR/legion_common.py" switch "${1:-list}"
