#!/usr/bin/env bash
# Build and install Legion plus its control tools.

set -euo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_BIN_DIR="${LEGION_BIN_DIR:-$HOME/.local/bin}"
INSTALL_SHARE_DIR="${LEGION_SHARE_DIR:-$HOME/.local/share/legion}"
INSTALL_TOOLS_DIR="$INSTALL_SHARE_DIR/tools"
GROK_CONFIG_HOME="${GROK_HOME:-$HOME/.grok}"
GROK_BIN_DIR="$GROK_CONFIG_HOME/bin"
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

mkdir -p -- "$INSTALL_BIN_DIR" "$INSTALL_TOOLS_DIR" "$GROK_BIN_DIR" "$PRESETS_DIR"
chmod 700 "$GROK_CONFIG_HOME" "$GROK_BIN_DIR" "$PRESETS_DIR" 2>/dev/null || true

echo "🚚 Installing runtime and control tools..."
install -m 0755 "$BINARY" "$INSTALL_BIN_DIR/xai-grok-pager"
install -m 0755 "$PROJECT_DIR/bin/legion" "$INSTALL_BIN_DIR/legion"

# ~/.grok/tools is the runtime home for dag-* helpers used by the TUI / LaunchAgents.
GROK_TOOLS_DIR="$GROK_CONFIG_HOME/tools"
mkdir -p -- "$GROK_TOOLS_DIR"
chmod 700 "$GROK_TOOLS_DIR" 2>/dev/null || true

for tool in \
    legion_common.py \
    auto-discover.py \
    legion-config.py \
    legion-hub.py \
    legion-mode.py \
    switch-subagents.sh \
    dag-switch.sh \
    dag-health.sh \
    dag-watch.sh \
    dag-watch-daemon.sh \
    dag-utilization.sh \
    dag-preset-smoke.py
do
    if [ -f "$PROJECT_DIR/tools/$tool" ]; then
        install -m 0755 "$PROJECT_DIR/tools/$tool" "$INSTALL_TOOLS_DIR/$tool"
        # Mirror into ~/.grok/tools so LaunchAgents and `dag` symlinks keep working
        install -m 0755 "$PROJECT_DIR/tools/$tool" "$GROK_TOOLS_DIR/$tool"
    fi
done

# Legacy / alternate presets (big-pickle, venice, etc.)
for preset in "$PROJECT_DIR"/presets/*.toml; do
    [ -f "$preset" ] || continue
    install -m 0600 "$preset" "$PRESETS_DIR/$(basename -- "$preset")"
done

# Labeled /dag presets (FULL | MIXED | ECONOMY) — source of truth under tools/dag-presets/
if [ -d "$PROJECT_DIR/tools/dag-presets" ]; then
    for preset in "$PROJECT_DIR"/tools/dag-presets/*.toml; do
        [ -f "$preset" ] || continue
        install -m 0644 "$preset" "$PRESETS_DIR/$(basename -- "$preset")"
    done
    # Keep legacy aliases in sync with the labeled presets
    if [ -f "$PRESETS_DIR/full-dag.toml" ]; then
        install -m 0644 "$PRESETS_DIR/full-dag.toml" "$PRESETS_DIR/best-value-dag.toml"
    fi
    if [ -f "$PRESETS_DIR/economy-dag.toml" ]; then
        install -m 0644 "$PRESETS_DIR/economy-dag.toml" "$PRESETS_DIR/deepseek-cost-dag.toml"
    fi
fi

ln -sfn "legion" "$INSTALL_BIN_DIR/grok"
# The updater atomically replaces these managed entry points with binaries from
# Legion GitHub releases. Seed all of them with the freshly built local binary
# so no direct command can fall through to an old upstream Grok installation.
for entrypoint in legion grok agent; do
    ln -sfn "$INSTALL_BIN_DIR/xai-grok-pager" "$GROK_BIN_DIR/$entrypoint"
done
ln -sfn "$INSTALL_TOOLS_DIR" "$INSTALL_BIN_DIR/.legion-tools"
ln -sfn "$INSTALL_TOOLS_DIR/legion-hub.py" "$INSTALL_BIN_DIR/legion-hub"
ln -sfn "$INSTALL_TOOLS_DIR/legion-mode.py" "$INSTALL_BIN_DIR/legion-mode"
ln -sfn "$INSTALL_TOOLS_DIR/legion-config.py" "$INSTALL_BIN_DIR/legion-config"
ln -sfn "$GROK_TOOLS_DIR/dag-switch.sh" "$INSTALL_BIN_DIR/dag"
ln -sfn "$GROK_TOOLS_DIR/dag-watch.sh" "$INSTALL_BIN_DIR/dag-watch"
ln -sfn "$GROK_TOOLS_DIR/dag-utilization.sh" "$INSTALL_BIN_DIR/dag-utilization"

# Optional: install/refresh dag-watch LaunchAgent (real-time subagent failure alerts)
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
DAG_WATCH_PLIST="$LAUNCH_AGENTS_DIR/com.michaelnichols.dag-watch.plist"
if [ "$(uname -s)" = "Darwin" ]; then
    mkdir -p -- "$LAUNCH_AGENTS_DIR"
    cat >"$DAG_WATCH_PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.michaelnichols.dag-watch</string>
    <key>ProgramArguments</key>
    <array>
        <string>$GROK_TOOLS_DIR/dag-watch-daemon.sh</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$GROK_CONFIG_HOME/logs/dag-watch.log</string>
    <key>StandardErrorPath</key>
    <string>$GROK_CONFIG_HOME/logs/dag-watch.log</string>
</dict>
</plist>
PLIST
    mkdir -p -- "$GROK_CONFIG_HOME/logs"
    # Load if possible; ignore failures in headless/CI environments.
    launchctl bootout "gui/$(id -u)/com.michaelnichols.dag-watch" 2>/dev/null || true
    launchctl bootstrap "gui/$(id -u)" "$DAG_WATCH_PLIST" 2>/dev/null \
        || launchctl load "$DAG_WATCH_PLIST" 2>/dev/null \
        || true
    echo "🔔 dag-watch LaunchAgent installed (macOS subagent failure notifications)."
fi

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
echo "   • Presets:       legion mode  |  dag full|mixed|economy"
echo "   • Role editor:   legion config"
echo "   • Re-discover:   legion discover"
echo "   • Failure alerts: dag-watch status|on|off"
echo "   • Model smoke:   python3 ~/.grok/tools/dag-preset-smoke.py"
echo
echo "After install or preset switch: restart the TUI (config binds at startup)."
if [[ ":$PATH:" != *":$INSTALL_BIN_DIR:"* ]]; then
    echo
    echo "Add $INSTALL_BIN_DIR to PATH before using these commands."
fi
echo "=========================================================="
