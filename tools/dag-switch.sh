#!/usr/bin/env bash
# dag-switch.sh — toggle between labeled DAG presets (FULL | ECONOMY | MIXED).
#
# Usage:
#   dag full|max|flagship|best
#   dag economy|cheap|daily|cost
#   dag status|which
#   dag list
#
# After switching: RESTART the Grok TUI from a fresh terminal (config binds at session start).
# Active label is written to ~/.grok/dag-mode (plain text: full|economy|mixed).
# Last switch timestamp is written to ~/.grok/dag-mode-switched-at (FT-006).

set -euo pipefail

PRESET_DIR="${GROK_PRESET_DIR:-$HOME/.grok/config-presets}"
CONFIG="${GROK_CONFIG:-$HOME/.grok/config.toml}"
MODE_FILE="${GROK_DAG_MODE:-$HOME/.grok/dag-mode}"
SWITCHED_AT_FILE="${GROK_DAG_SWITCHED_AT:-$HOME/.grok/dag-mode-switched-at}"
BACKUP_DIR="${GROK_CONFIG_BACKUP_DIR:-$HOME/.grok}"

die() { echo "dag: error: $*" >&2; exit 1; }
info() { echo "dag: $*"; }

normalize() {
  local a
  a="$(echo "${1:-}" | tr '[:upper:]' '[:lower:]' | tr -d '[:space:]')"
  case "$a" in
    full|max|flagship|best|best-value|bestvalue) echo full ;;
    economy|econ|cheap|daily|cost|deepseek|budget) echo economy ;;
    mixed|diverse|multi-family|multifamily|ensemble|cross|cross-family) echo mixed ;;
    status|which|show|?) echo status ;;
    list|ls|presets) echo list ;;
    help|-h|--help) echo help ;;
    "") echo status ;;
    *) echo unknown ;;
  esac
}

preset_path() {
  case "$1" in
    full) echo "$PRESET_DIR/full-dag.toml" ;;
    mixed) echo "$PRESET_DIR/mixed-dag.toml" ;;
    economy) echo "$PRESET_DIR/economy-dag.toml" ;;
    *) die "no preset for mode '$1'" ;;
  esac
}

print_restart_banner() {
  local mode="${1:-unknown}"
  echo
  echo "╔══════════════════════════════════════════════════════════╗"
  echo "║  RESTART REQUIRED — config binds at TUI session start    ║"
  printf "║  Disk now: %-10s | Live session: STILL OLD until     ║\n" "$mode"
  echo "║  restart                                                 ║"
  echo "║  1. Quit grok fully (Cmd+Q / /quit)                      ║"
  echo "║  2. Open a fresh terminal                                ║"
  echo "║  3. Run: grok                                            ║"
  echo "║  Until then: dag-summary/disk can say MIXED while spawns ║"
  echo "║  still use the previous preset's models. (FT-006)        ║"
  echo "╚══════════════════════════════════════════════════════════╝"
  echo
}

print_bind_warning() {
  echo "WARNING: Config binds at TUI session start only."
  echo "  If the TUI was launched before the last \`dag\` switch, live"
  echo "  subagent routing may still be the PREVIOUS preset."
  echo "  Restart grok after every switch. Disk label can lie until then."
  if [[ -f "$SWITCHED_AT_FILE" ]]; then
    local switched_mode switched_at
    switched_mode="$(sed -n '1p' "$SWITCHED_AT_FILE" | tr -d '[:space:]')"
    switched_at="$(sed -n '2p' "$SWITCHED_AT_FILE" | tr -d '[:space:]')"
    if [[ -n "$switched_mode" || -n "$switched_at" ]]; then
      echo "Last disk switch : ${switched_mode:-?} at ${switched_at:-?}"
      echo "  → Restart TUI if the running session is older than this switch."
    fi
  fi
}

show_status() {
  local mode="(unknown)"
  if [[ -f "$MODE_FILE" ]]; then
    mode="$(tr -d '[:space:]' <"$MODE_FILE")"
  fi
  local def=""
  if [[ -f "$CONFIG" ]]; then
    def="$(grep -E '^\s*default\s*=' "$CONFIG" | tail -1 | sed 's/.*=\s*//' | tr -d ' "')"
  fi
  echo "Active DAG label : ${mode}"
  echo "Mode file        : $MODE_FILE"
  echo "Config           : $CONFIG"
  echo "[models] default : ${def:-?}"
  echo
  print_bind_warning
  echo
  case "$mode" in
    full)
      echo "FULL = flagship multi-vendor (Grok main, Claude plan/impl, GPT architect, DeepSeek verify)"
      echo "Use for complex / stuck tasks. Cost: HIGH."
      ;;
    economy)
      echo "ECONOMY = DeepSeek-primary DAG (flash explore, pro elsewhere). Cost: LOW–MEDIUM."
      echo "Use for simple/daily work. Escalate to FULL when stuck."
      ;;
    mixed)
      echo "MIXED  = multi-family economy DAG (DeepSeek main/impl, MiniMax plan/architect, Qwen verify)"
      echo "Use for daily work with true cross-family verification. Cost: LOW–MEDIUM."
      ;;
    *)
      echo "Unknown/missing label — run:  dag full   or   dag economy"
      ;;
  esac
  echo
  echo "Switch:  dag full  |  dag mixed  |  dag economy"
  echo "Then:    restart the Grok TUI (quit fully, open from a fresh terminal)."
}

list_presets() {
  echo "Labeled DAGs:"
  echo "  full     → $PRESET_DIR/full-dag.toml"
  echo "  mixed    → $PRESET_DIR/mixed-dag.toml"
  echo "  economy  → $PRESET_DIR/economy-dag.toml"
  echo
  echo "Aliases:"
  echo "  full     = max, flagship, best"
  echo "  mixed    = diverse, multi-family, ensemble, cross"
  echo "  economy  = cheap, daily, cost"
  if [[ -d "$PRESET_DIR" ]]; then
    echo
    echo "Other files in $PRESET_DIR:"
    ls -1 "$PRESET_DIR"/*.toml 2>/dev/null | sed 's|.*/|  |' || true
  fi
}

show_help() {
  cat <<'EOF'
dag — switch Grok Build DAG presets (FULL | MIXED | ECONOMY)

  dag full       Flagship multi-vendor DAG (expensive, most capable)
  dag economy    DeepSeek-primary DAG (cheap daily driver)
  dag mixed      Multi-family economy DAG (cross-family verification)
  dag status     Show which label is active
  dag list       List presets / aliases

After every switch you MUST restart the Grok TUI.
Config binds at session start — chat alone cannot change models mid-session.
Disk label (~/.grok/dag-mode) can lie about live routing until restart (FT-006).

Examples:
  dag economy && echo "now restart grok"
  dag full
  dag status
EOF
}

apply_mode() {
  local mode="$1"
  local src
  src="$(preset_path "$mode")"
  [[ -f "$src" ]] || die "preset missing: $src"
  [[ -f "$CONFIG" ]] || die "config missing: $CONFIG"

  local ts bak
  ts="$(date +%Y%m%d-%H%M%S)"
  bak="${BACKUP_DIR}/config.toml.bak-dag-${mode}-${ts}"
  cp -p "$CONFIG" "$bak"
  cp "$src" "$CONFIG"
  # Keep best-value-dag.toml in sync when applying full (legacy name in docs)
  if [[ "$mode" == "full" ]]; then
    cp "$src" "$PRESET_DIR/best-value-dag.toml"
  fi
  # Legacy cost preset stays aligned with economy
  if [[ "$mode" == "economy" ]]; then
    cp "$src" "$PRESET_DIR/deepseek-cost-dag.toml" 2>/dev/null || true
  fi

  printf '%s\n' "$mode" >"$MODE_FILE"
  # FT-006: durable switch stamp so `dag status` can warn about stale sessions
  {
    printf '%s\n' "$mode"
    date -u +"%Y-%m-%dT%H:%M:%SZ"
  } >"$SWITCHED_AT_FILE"

  info "switched → ${mode}"
  info "preset    $src"
  info "wrote     $CONFIG"
  info "backup    $bak"
  info "label     $MODE_FILE  (= $mode)"
  info "switched  $SWITCHED_AT_FILE"
  print_restart_banner "$mode"
  show_status
}

cmd="$(normalize "${1:-status}")"
case "$cmd" in
  help) show_help ;;
  list) list_presets ;;
  status) show_status ;;
  full|mixed|economy) apply_mode "$cmd" ;;
  unknown) die "unknown mode '${1:-}'. Try: dag full | dag mixed | dag economy | dag status" ;;
  *) die "internal: unhandled '$cmd'" ;;
esac
