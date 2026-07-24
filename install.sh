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
for name in "legion" "grok"; do
    target="$HOME/.local/bin/$name"
    if [ -L "$target" ] || [ -f "$target" ]; then
        echo "🧹 Removing legacy $name binary/symlink at $target..."
        rm -f "$target"
    fi
done

# Run auto-discovery
echo "⚡ Running Zero-Touch Provider & Model Auto-Discovery..."
python3 tools/auto-discover.py
./tools/switch-subagents.sh auto-discovered

# Install launcher script for both 'legion' and 'grok' commands
cp bin/legion ~/.local/bin/legion
chmod +x ~/.local/bin/legion

cp bin/legion ~/.local/bin/grok
chmod +x ~/.local/bin/grok

echo ""
echo "=========================================================="
echo "✅ Legion Grok Fork successfully installed!"
echo "   Run 'legion' or 'grok' from anywhere to start your session."
echo "=========================================================="
