#!/usr/bin/env bash
# Build and install Legion plus its control tools.

set -euo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_BIN_DIR="${LEGION_BIN_DIR:-$HOME/.local/bin}"
INSTALL_SHARE_DIR="${LEGION_SHARE_DIR:-$HOME/.local/share/legion}"
INSTALL_TOOLS_DIR="$INSTALL_SHARE_DIR/tools"
GROK_CONFIG_HOME="${GROK_HOME:-$HOME/.grok}"
PRESETS_DIR="$GROK_CONFIG_HOME/config-presets"

cd -- "$PROJECT_DIR"

echo "🚀 Installing Legion..."
if [ "${LEGION_SKIP_BUILD:-0}" != "1" ]; then
    echo "📦 Building the release binary..."
    cargo build --release -p xai-grok-pager-bin
fi

BINARY="$PROJECT_DIR/target/release/xai-grok-pager"
if [ ! -x "$BINARY" ]; then
    echo "Error: release binary not found at $BINARY" >&2
    exit 1
fi

mkdir -p -- "$INSTALL_BIN_DIR" "$INSTALL_TOOLS_DIR" "$PRESETS_DIR"
chmod 700 "$GROK_CONFIG_HOME" "$PRESETS_DIR" 2>/dev/null || true

echo "🚚 Installing runtime and control tools..."
install -m 0755 "$BINARY" "$INSTALL_BIN_DIR/xai-grok-pager"
install -m 0755 "$PROJECT_DIR/bin/legion" "$INSTALL_BIN_DIR/legion"

for tool in \
    legion_common.py \
    auto-discover.py \
    legion-config.py \
    legion-hub.py \
    legion-mode.py \
    switch-subagents.sh
do
    install -m 0755 "$PROJECT_DIR/tools/$tool" "$INSTALL_TOOLS_DIR/$tool"
done

for preset in "$PROJECT_DIR"/presets/*.toml; do
    install -m 0600 "$preset" "$PRESETS_DIR/$(basename -- "$preset")"
done

ln -sfn "legion" "$INSTALL_BIN_DIR/grok"
ln -sfn "$INSTALL_TOOLS_DIR" "$INSTALL_BIN_DIR/.legion-tools"
ln -sfn "$INSTALL_TOOLS_DIR/legion-hub.py" "$INSTALL_BIN_DIR/legion-hub"
ln -sfn "$INSTALL_TOOLS_DIR/legion-mode.py" "$INSTALL_BIN_DIR/legion-mode"
ln -sfn "$INSTALL_TOOLS_DIR/legion-config.py" "$INSTALL_BIN_DIR/legion-config"

if [ ! -f "$GROK_CONFIG_HOME/config.toml" ]; then
    echo "⚡ Generating and activating an auto-discovered profile..."
    python3 "$INSTALL_TOOLS_DIR/auto-discover.py" --activate
else
    echo "🔒 Preserving the existing active configuration."
    if [ ! -f "$PRESETS_DIR/auto-discovered.toml" ]; then
        echo "⚡ Generating an optional auto-discovered profile..."
        python3 "$INSTALL_TOOLS_DIR/auto-discover.py"
    fi
fi

echo
echo "=========================================================="
echo "✅ Legion installed successfully."
echo "   • Start:         legion"
echo "   • Control hub:   legion hub"
echo "   • Presets:       legion mode"
echo "   • Role editor:   legion config"
echo "   • Re-discover:   legion discover"
if [[ ":$PATH:" != *":$INSTALL_BIN_DIR:"* ]]; then
    echo
    echo "Add $INSTALL_BIN_DIR to PATH before using these commands."
fi
echo "=========================================================="
