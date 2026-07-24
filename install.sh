#!/bin/bash
# Install script for Legion Grok Fork

set -e

echo "🚀 Installing Legion Grok Fork..."

# Build release binary
echo "📦 Building release binary..."
cargo build --release -p xai-grok-pager-bin

# Ensure ~/.local/bin exists
mkdir -p ~/.local/bin

# Automatically remove any pre-existing legacy symlinks or binaries
for name in "legion" "grok" "legion-hub" "legion-mode" "legion-config" "xai-grok-pager" "xai-grok-pager-bin"; do
    target="$HOME/.local/bin/$name"
    if [ -L "$target" ] || [ -f "$target" ]; then
        echo "🧹 Removing legacy $name binary/symlink at $target..."
        rm -f "$target"
    fi
done

# Copy release binary to ~/.local/bin/xai-grok-pager
echo "🚚 Installing binary to ~/.local/bin/xai-grok-pager..."
cp target/release/xai-grok-pager ~/.local/bin/xai-grok-pager
chmod +x ~/.local/bin/xai-grok-pager

# Run auto-discovery
echo "⚡ Running Zero-Touch Provider & Model Auto-Discovery..."
python3 tools/auto-discover.py
./tools/switch-subagents.sh auto-discovered

# Install launcher script for 'legion' and 'grok' commands
cp bin/legion ~/.local/bin/legion
chmod +x ~/.local/bin/legion

cp bin/legion ~/.local/bin/grok
chmod +x ~/.local/bin/grok

# Install interactive hub, mode selector, and config editor tools
cp tools/legion-hub.py ~/.local/bin/legion-hub
chmod +x ~/.local/bin/legion-hub

cp tools/legion-mode.py ~/.local/bin/legion-mode
chmod +x ~/.local/bin/legion-mode

cp tools/legion-config.py ~/.local/bin/legion-config
chmod +x ~/.local/bin/legion-config

echo ""
echo "=========================================================="
echo "✅ Legion Grok Fork successfully installed!"
echo "   • Run 'legion' or 'grok' to start your session."
echo "   • Run 'legion-hub' or 'legion hub' for the interactive Hub."
echo "   • Run 'legion-mode' to switch DAG preset profiles."
echo "   • Run 'legion-config' to easily edit models per role."
echo "=========================================================="
