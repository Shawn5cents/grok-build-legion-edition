#!/bin/bash
# dag-health.sh — monitors the Grok Build DAG for broken providers.
#
# Checks (designed to run every 60s via LaunchAgent, or manually):
#   1. The running TUI process (xai-grok-pager) has DEEPSEEK_API_KEY,
#      ANTHROPIC_API_KEY, OPENAI_API_KEY and XAI_API_KEY in ITS environment.
#      (Missing env = provider subagents silently fall back to the session JWT
#       and 401 — the DAG looks healthy but never calls the provider.)
#   2. ~/.grok/logs/unified.jsonl for recent inference/auth failures, and for
#      claude/gpt model resolutions that fell back to SessionToken auth.
#
# ALERTING (redesigned 2026-07-31): problems raise ONE persistent macOS alert
# (osascript `display alert ... as critical`) that stays on screen until the user
# clicks it — no auto-dismissing banner, no timed re-nag sawtooth.
#
# DISMISSAL-BASED DEDUPE (no timestamps in signatures):
#   * Each detected problem gets a stable signature per problem CLASS:
#       envkey:<KEY_NAME>   a key missing from the TUI process env
#       logfail:<kind>      inference_failed | Authentication_Fails | Unauthorized_(401)
#       sess                a claude/gpt model resolved with SessionToken
#   * $STATE (~/.grok/logs/dag-health.last) is the list of signatures the user has
#     ALREADY dismissed — one whitespace-free token per line, no epoch. Signatures
#     listed there are silent forever (no re-nag).
#   * Signatures not listed are collected during the run; at the end a single
#     critical alert lists them all and BLOCKS until dismissed. Only after the
#     dialog returns are the shown signatures appended to $STATE (atomic tmp+mv).
#   * If osascript fails (no GUI/Aqua session), the alert is only logged and
#     NOTHING is marked dismissed, so a later run retries.
#   * LaunchAgent StartInterval=60 will not start an overlapping run while the
#     script blocks on the dialog, so dialogs cannot stack.
#
# RE-ENABLE ALERTS (forget all dismissals):  : > ~/.grok/logs/dag-health.last
#
# Exit 0 = healthy, 1 = problems found.

set -u
LOG_DIR="$HOME/.grok/logs"
LOG="$LOG_DIR/unified.jsonl"
STATE="$LOG_DIR/dag-health.last"
LOOKBACK_MIN=15

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

# Signatures collected this run (whitespace-free tokens) + human-readable details.
PENDING_SIGS=""
PENDING_MSGS=""

# Make arbitrary text safe for AppleScript: drop backslashes and double quotes
# (they would break a string literal), flatten CR/TAB to spaces, keep newlines as
# line separators, cap each line at 200 chars and the whole message at 8 lines.
sanitize() {
  printf '%s' "$1" | tr -d '\\"' | tr '\r\t' '  ' | cut -c1-200 | head -8
}

# Persistent modal alert: stays on screen until the user clicks it.
# Text is passed via `on run argv` (not string interpolation) so quoting/newlines
# cannot corrupt the AppleScript; sanitize() is belt-and-braces on top of that.
# Returns 0 if the dialog was actually shown+dismissed, 1 if osascript failed.
alert_blocking() {
  local title msg
  title=$(sanitize "$1")
  msg=$(sanitize "$2")
  log "ALERT (waiting for dismissal): $title — $(printf '%s' "$msg" | tr '\n' '|')"
  if osascript \
      -e 'on run argv' \
      -e 'display alert (item 1 of argv) message (item 2 of argv) as critical' \
      -e 'end run' \
      -- "$title" "$msg" >/dev/null 2>&1; then
    log "alert dismissed by user"
    return 0
  fi
  log "osascript failed (no GUI session?) — alert logged only, NOT marked dismissed"
  return 1
}

# Read $STATE into a newline-delimited list of valid signature tokens.
# The format is ONE whitespace-free token per line. Malformed lines are dropped,
# never evaluated: this includes empty lines and legacy "<sig> <epoch>" lines from
# the old timestamp scheme, plus any sig that picked up spaces from a JSON blob.
# (The old code did `$(( NOW_EPOCH - e ))` on that trailing field; a non-numeric
# value made bash resolve it as a variable NAME -> "logfail: unbound variable"
# under `set -u`, killing the script mid-check. No arithmetic is done on state
# fields at all now, and the guard below discards junk instead of dying.)
dismissed_sigs() {
  [ -f "$STATE" ] || return 0
  local line
  while IFS= read -r line; do
    case "$line" in
      '') continue ;;                 # empty line -> prune
      *[[:space:]]*) continue ;;      # legacy "<sig> <epoch>" / corrupt -> prune
    esac
    printf '%s\n' "$line"
  done < "$STATE"
}

DISMISSED=$(dismissed_sigs)

is_dismissed() {
  local sig="$1"
  printf '%s\n' "$DISMISSED" | grep -qxF "$sig"
}

# Queue a problem for this run's single alert (unless already dismissed).
# $1 = signature (no whitespace), $2 = human-readable detail line
queue_problem() {
  local sig="$1" msg="$2"
  # Defensive: signatures must be whitespace-free tokens.
  sig=$(printf '%s' "$sig" | tr -d '[:space:]')
  [ -n "$sig" ] || return 0
  if is_dismissed "$sig"; then
    log "already dismissed (silent): $sig"
    return 0
  fi
  # already queued this run? (exact whole-line match, not substring)
  if printf '%s' "$PENDING_SIGS" | grep -qxF "$sig"; then
    return 0
  fi
  PENDING_SIGS="${PENDING_SIGS}${sig}"$'\n'
  PENDING_MSGS="${PENDING_MSGS}${msg}"$'\n'
}

# Show the single alert (if anything queued) and record dismissals atomically.
flush_problems() {
  [ -n "$PENDING_SIGS" ] || return 0
  local body
  body=$(printf '%s' "$PENDING_MSGS")
  if alert_blocking "DAG BROKEN" "$body"; then
    local tmp="$STATE.tmp.$$"
    { dismissed_sigs; printf '%s' "$PENDING_SIGS"; } > "$tmp" && mv -f "$tmp" "$STATE"
    rm -f "$tmp" 2>/dev/null || true
    log "recorded dismissal for: $(printf '%s' "$PENDING_SIGS" | tr '\n' ' ')"
  fi
}

PROBLEMS=0

# --- 1. TUI process environment -------------------------------------------
# Match on comm (exact executable name), NOT args: this watcher's own awk/bash
# processes contain "xai-grok-pager" in their command line, so matching args
# picked a keyless process and false-alerted "keys missing" every minute even
# though the real TUI had all keys. (pgrep -f has the same self-match problem
# under the TUI's wrapped shell.)
# macOS ps -o comm= returns the FULL executable path, so match the basename suffix.
TUI_PID=$(ps -axo pid=,comm= | awk '$2 ~ /\/xai-grok-pager$/ || $2 == "xai-grok-pager" {print $1; exit}')
if [ -n "$TUI_PID" ]; then
  TUI_ENV=$(ps -ww -p "$TUI_PID" -E 2>/dev/null)
  for VAR in DEEPSEEK_API_KEY ANTHROPIC_API_KEY OPENAI_API_KEY XAI_API_KEY; do
    if ! echo "$TUI_ENV" | tr ' ' '\n' | grep -q "^$VAR=..*"; then
      PROBLEMS=1
      queue_problem "envkey:$VAR" \
        "$VAR missing from TUI process (pid $TUI_PID) — restart grok from a shell that sourced ~/.zshrc; that provider 401s until then."
    fi
  done
else
  log "no running TUI (xai-grok-pager) — skipping env check"
fi

# --- 2. Recent log failures ------------------------------------------------
if [ -f "$LOG" ]; then
  CUTOFF=$(date -u -v-${LOOKBACK_MIN}M +%Y-%m-%dT%H:%M:%S)

  # 2a. hard failure markers in the window
  FAIL_LINES=$(awk -v c="$CUTOFF" 'substr($0,8,19) >= c' "$LOG" \
    | grep -E "inference_failed|Authentication Fails|Unauthorized \(401\)" | tail -1)
  if [ -n "$FAIL_LINES" ]; then
    PROBLEMS=1
    TS=$(echo "$FAIL_LINES" | sed -E 's/.*"ts":"([^"]+)".*/\1/')
    [ "$TS" = "$FAIL_LINES" ] && TS="recent"
    MSG=$(echo "$FAIL_LINES" | sed -E 's/.*"message":"([^"]{0,140}).*/\1/')
    [ "$MSG" = "$FAIL_LINES" ] && MSG="inference/auth failure in log (see unified.jsonl)"
    # Signature = problem CLASS only (first marker matched), never the timestamp:
    # embedding the ts minted a fresh signature per log line, which is what caused
    # the endless re-nag sawtooth. Spaces are normalized to underscores.
    KIND=$(echo "$FAIL_LINES" \
      | grep -oE "inference_failed|Authentication Fails|Unauthorized \(401\)" \
      | head -1 | tr ' ' '_')
    [ -n "$KIND" ] || KIND="unknown"
    queue_problem "logfail:$KIND" "inference/auth failure ($KIND) at $TS: $MSG"
  fi

  # 2b. claude/gpt models resolved with SessionToken (API key not attached)
  SESS_LINES=$(awk -v c="$CUTOFF" 'substr($0,8,19) >= c' "$LOG" \
    | grep -E '"model_id":"(claude-opus-5|gpt-5.6-sol|gpt-5.6-luna)"' \
    | grep '"auth_type":"SessionToken"' | tail -1)
  if [ -n "$SESS_LINES" ]; then
    PROBLEMS=1
    TS=$(echo "$SESS_LINES" | sed -E 's/.*"ts":"([^"]+)".*/\1/')
    [ "$TS" = "$SESS_LINES" ] && TS="recent"
    queue_problem "sess" \
      "A claude/gpt model resolved with SessionToken instead of its API key (at $TS). Check TUI env and config."
  fi
fi

# One blocking critical alert for everything new this run; dismissal is recorded
# only after the user closes it.
flush_problems

if [ "$PROBLEMS" -eq 0 ]; then
  log "DAG HEALTHY (env keys present, no recent failures)"
fi
exit "$PROBLEMS"
