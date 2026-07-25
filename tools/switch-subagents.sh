#!/bin/bash
# Switch between subagent model presets for multi-agent DAGs
# Usage: ./tools/switch-subagents.sh [default|legion-dag|cline-pass-dag|flash-orchestrator|deepseek-pro-only|list]

set -e

CONFIG="$HOME/.grok/config.toml"
PRESETS_DIR="$HOME/.grok/config-presets"
PRESET="${1:-list}"

if [ "$PRESET" = "list" ]; then
    echo "Available Subagent DAG Presets:"
    mkdir -p "$PRESETS_DIR"
    for f in "$PRESETS_DIR"/*.toml; do
        [ -f "$f" ] || continue
        name=$(basename "$f" .toml)
        echo "  - $name"
    done
    echo ""
    echo "Current [subagents.models] in $CONFIG:"
    grep -A 10 '\[subagents.models\]' "$CONFIG" 2>/dev/null || echo "No [subagents.models] section found."
    exit 0
fi

PRESET_FILE="$PRESETS_DIR/$PRESET.toml"
if [ ! -f "$PRESET_FILE" ]; then
    echo "Error: preset '$PRESET' not found at $PRESET_FILE"
    exit 1
fi

python3 -c "
import sys, re

config_path = '$CONFIG'
preset_path = '$PRESET_FILE'
preset_name = sys.argv[1]

with open(config_path) as f:
    config = f.read()

pattern = r'(\[subagents\.models\]\n)((?:.*\n)*?)(?=\n\[|$)'
match = re.search(pattern, config)

with open(preset_path) as f:
    preset = f.read()

preset_match = re.search(r'\[subagents\.models\]\n((?:.+\n)*)', preset)
if preset_match:
    subagents_header = '[subagents]\nenabled = true\n\n'
    if '[subagents]' in config and '[subagents.models]' in config:
        pattern = r'(\[subagents\].*?\n\[subagents\.models\]\n)((?:.*\n)*?)(?=\n\[|$)'
        match = re.search(pattern, config, re.DOTALL)
        if match:
            new_block = '[subagents]\nenabled = true\n\n[subagents.models]\n' + preset_match.group(1)
            new_config = config[:match.start()] + new_block + config[match.end():]
        else:
            pattern_models = r'(\[subagents\.models\]\n)((?:.*\n)*?)(?=\n\[|$)'
            match_m = re.search(pattern_models, config)
            if match_m:
                new_block = '[subagents]\nenabled = true\n\n[subagents.models]\n' + preset_match.group(1)
                new_config = config[:match_m.start()] + new_block + config[match_m.end():]
            else:
                new_config = config + '\n' + subagents_header + '[subagents.models]\n' + preset_match.group(1)
    elif '[subagents.models]' in config:
        pattern_models = r'(\[subagents\.models\]\n)((?:.*\n)*?)(?=\n\[|$)'
        match_m = re.search(pattern_models, config)
        new_block = '[subagents]\nenabled = true\n\n[subagents.models]\n' + preset_match.group(1)
        new_config = config[:match_m.start()] + new_block + config[match_m.end():]
    else:
        new_config = config.rstrip() + '\n\n' + subagents_header + '[subagents.models]\n' + preset_match.group(1)
    with open(config_path, 'w') as f:
        f.write(new_config)
    print(f'Successfully switched DAG preset to: {preset_name}')
else:
    print('Error: invalid preset format')
    sys.exit(1)
" "$PRESET" 2>&1

echo ""
echo "Updated [subagents.models]:"
grep -A 10 '\[subagents.models\]' "$CONFIG"
