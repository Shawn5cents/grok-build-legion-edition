#!/usr/bin/env bash
# dag-watch-daemon.sh — LaunchAgent-compatible DAG failure monitor
# Runs in foreground. LaunchAgent keeps it alive.
#
# Watches ~/.grok/logs/unified.jsonl for subagent spawn/complete/fail events.
# On FAIL: logs + macOS Notification Center banner + sound.
#
# Why notifications used to silently fail:
#   Error strings often contain newlines, double-quotes, and backslashes.
#   Those broke the osascript one-liner; failures were swallowed by `2>/dev/null`.

set -u

LOG_FILE="${GROK_UNIFIED_LOG:-$HOME/.grok/logs/unified.jsonl}"
STATE_DIR="${XDG_STATE_HOME:-$HOME/.grok/logs}"
mkdir -p "$STATE_DIR" 2>/dev/null || true
LAST_POS_FILE="${DAG_WATCH_POS_FILE:-$STATE_DIR/dag-watch-daemon.lastpos}"
NOTIF_LOG="${DAG_WATCH_NOTIF_LOG:-$STATE_DIR/dag-watch-notify.log}"
WATCH_LOG="${DAG_WATCH_LOG:-$STATE_DIR/dag-watch.log}"

# Flatten any string into a single AppleScript-safe line.
as_safe() {
    # stdin → stdout: strip CRs, collapse newlines/tabs to spaces, escape \ and "
    tr '\r\n\t' '   ' | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g' | cut -c1-180
}

log_line() {
    # Always mirror to stdout (LaunchAgent captures → dag-watch.log)
    printf '%s\n' "$*"
}

notify_fail() {
    local role="$1" model="$2" error="$3" ts="$4"
    local title body subtitle
    title="DAG Subagent Failure"
    subtitle="$(printf '%s (%s)' "$role" "$model" | as_safe)"
    body="$(printf '%s' "$error" | as_safe)"
    [[ -z "$body" ]] && body="subagent failed (no error details)"

    log_line ""
    log_line "DAG FAIL | role=${role} model=${model} ts=${ts}"
    log_line "  error=${error}"

    # Record every notify attempt so we can prove delivery path.
    {
        printf '%s NOTIFY role=%s model=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$role" "$model"
        printf '  body=%s\n' "$body"
    } >>"$NOTIF_LOG" 2>/dev/null || true

    # 1) Primary: osascript Notification Center (sanitized single-line strings)
    local osa_err
    osa_err=$(osascript \
        -e "display notification \"${body}\" with title \"${title}\" subtitle \"${subtitle}\" sound name \"Basso\"" \
        2>&1) || {
        printf '%s osascript FAILED: %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$osa_err" >>"$NOTIF_LOG" 2>/dev/null || true
        log_line "  notify-osascript-error: $osa_err"
    }

    # 2) Fallback: terminal-notifier if installed (more reliable on some macOS versions)
    if command -v terminal-notifier >/dev/null 2>&1; then
        terminal-notifier \
            -title "$title" \
            -subtitle "$role ($model)" \
            -message "$(printf '%s' "$error" | tr '\r\n\t' '   ' | cut -c1-180)" \
            -sound Basso \
            >/dev/null 2>&1 || true
    fi

    # 3) Fallback: afplay system sound so something is always audible
    if [[ -f /System/Library/Sounds/Basso.aiff ]]; then
        afplay /System/Library/Sounds/Basso.aiff >/dev/null 2>&1 &
    fi
}

spawn_msg() {
    log_line "$(printf 'SPAWN | role=%-16s model=%s' "$1" "$2")"
}

complete_msg() {
    log_line "$(printf 'DONE  | role=%-16s model=%-22s %sms' "$1" "$2" "$3")"
}

if [[ ! -f "$LOG_FILE" ]]; then
    log_line "dag-watch-daemon: log file not found: $LOG_FILE (retrying in 10s)"
    sleep 10
    exit 0
fi

# Resume from last byte offset if present; otherwise start at EOF (don't replay history).
if [[ -f "$LAST_POS_FILE" ]]; then
    pos=$(cat "$LAST_POS_FILE" 2>/dev/null || echo 0)
else
    pos=$(wc -c <"$LOG_FILE" 2>/dev/null | tr -d ' ' || echo 0)
fi
# Clamp if log was rotated/truncated
current_size=$(wc -c <"$LOG_FILE" 2>/dev/null | tr -d ' ' || echo 0)
if [[ "${pos:-0}" -gt "${current_size:-0}" ]]; then
    pos=$current_size
fi
echo "$pos" >"$LAST_POS_FILE"

log_line "dag-watch-daemon: monitoring $LOG_FILE (pid=$$ pos=$pos)"
log_line "dag-watch-daemon: notify log → $NOTIF_LOG"

# Single python helper per chunk — far faster than 6 python invocations per line.
process_chunk() {
    python3 - "$1" <<'PY'
import json, sys
path = sys.argv[1]
try:
    data = open(path, "r", encoding="utf-8", errors="replace").read()
except OSError as e:
    print(f"ERR\tread\t{e}", flush=True)
    raise SystemExit(0)
for line in data.splitlines():
    line = line.strip()
    if not line:
        continue
    try:
        d = json.loads(line)
    except Exception:
        continue
    msg = d.get("msg") or ""
    if msg not in ("subagent spawn credentials", "subagent failed", "subagent completed"):
        continue
    ctx = d.get("ctx") or {}
    role = ctx.get("subagent_type") or "unknown"
    model = ctx.get("effective_model") or "unknown"
    ts = d.get("ts") or ""
    if msg == "subagent spawn credentials":
        print(f"SPAWN\t{role}\t{model}", flush=True)
    elif msg == "subagent completed":
        dur = ctx.get("duration_ms", "?")
        print(f"DONE\t{role}\t{model}\t{dur}", flush=True)
    else:
        err = ctx.get("error") or "no error details"
        # collapse whitespace for the TSV field; full error still useful
        err_one = " ".join(str(err).split())
        print(f"FAIL\t{role}\t{model}\t{ts}\t{err_one}", flush=True)
PY
}

while true; do
    current_size=$(wc -c <"$LOG_FILE" 2>/dev/null | tr -d ' ' || echo 0)
    if [[ "${current_size:-0}" -lt "${pos:-0}" ]]; then
        # log rotated
        pos=0
    fi
    if [[ "${current_size:-0}" -gt "${pos:-0}" ]]; then
        tmp=$(mktemp -t dag-watch-chunk.XXXXXX)
        # Portable byte slice
        dd if="$LOG_FILE" bs=1 skip="$pos" count=$((current_size - pos)) of="$tmp" 2>/dev/null || {
            # fallback
            tail -c +"$((pos + 1))" "$LOG_FILE" >"$tmp" 2>/dev/null || true
        }
        while IFS=$'\t' read -r kind a b c d; do
            case "$kind" in
                SPAWN) spawn_msg "$a" "$b" ;;
                DONE)  complete_msg "$a" "$b" "$c" ;;
                FAIL)  notify_fail "$a" "$b" "$d" "$c" ;;
                ERR)   log_line "dag-watch parse error: $a $b" ;;
            esac
        done < <(process_chunk "$tmp")
        rm -f "$tmp"
        pos=$current_size
        echo "$pos" >"$LAST_POS_FILE"
    fi
    sleep 1
done
