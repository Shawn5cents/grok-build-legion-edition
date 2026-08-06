#!/usr/bin/env bash
# dag-utilization.sh — DAG subagent utilization report
#
# Analyzes subagent spawn/completion events from the unified Grok log,
# compares actual model usage against the intended DAG config, and reports
# per-role success rates, deviations, and model usage breakdowns.
#
# Usage:
#   dag-utilization --lookback 1440          # last 24h (default)
#   dag-utilization --lookback 60 --json     # last 1h, JSON output
#   dag-utilization --role explore --role implementor
#   dag-utilization --failures-only
#   dag-utilization -h
#
# Exit codes: 0=healthy, 1=warning (deviations or low success), 2=critical (failures or jq missing)

set -euo pipefail

# ---------------------------------------------------------------------------
# Global paths
# ---------------------------------------------------------------------------
GROK_HOME="${GROK_HOME:-$HOME/.grok}"
LOG_FILE="$GROK_HOME/logs/unified.jsonl"
DAG_MODE_FILE="$GROK_HOME/dag-mode"
PRESETS_DIR="$GROK_HOME/config-presets"

# ---------------------------------------------------------------------------
# Pre-flight: jq required (exit 2)
# ---------------------------------------------------------------------------
if ! command -v jq >/dev/null 2>&1; then
    echo "ERROR: jq required for JSON log parsing" >&2
    exit 2
fi

# ---------------------------------------------------------------------------
# Helper: convert UTC timestamp to epoch seconds (macOS date compatible)
# Input: 2026-08-02T04:45:15.025Z
# Output: epoch seconds (integer)
# ---------------------------------------------------------------------------
ts_to_epoch() {
    local ts="$1"
    local clean
    clean="${ts%Z}"                         # strip trailing Z
    clean="${clean%%.*}"                    # strip fractional seconds
    date -j -u -f '%Y-%m-%dT%H:%M:%S' "$clean" '+%s' 2>/dev/null || echo "0"
}

# ---------------------------------------------------------------------------
# Helper: compute cutoff epoch from lookback minutes
# ---------------------------------------------------------------------------
cutoff_epoch() {
    local lookback_min="$1"
    local now_epoch cutoff_ts
    now_epoch=$(date -u '+%s')
    echo $(( now_epoch - (lookback_min * 60) ))
}

# ---------------------------------------------------------------------------
# Parse CLI arguments
# ---------------------------------------------------------------------------
LOOKBACK=1440
OUTPUT_JSON=false
FAILURES_ONLY=false
ROLE_FILTERS=""
HELP=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --lookback)
            LOOKBACK="$2"
            shift 2
            ;;
        --json)
            OUTPUT_JSON=true
            shift
            ;;
        --role)
            ROLE_FILTERS="${ROLE_FILTERS}${2}"$'\n'
            shift 2
            ;;
        --failures-only)
            FAILURES_ONLY=true
            shift
            ;;
        -h|--help)
            HELP=true
            shift
            ;;
        *)
            echo "Unknown option: $1" >&2
            echo "Usage: dag-utilization [--lookback N] [--json] [--role ROLE]... [--failures-only] [-h]" >&2
            exit 2
            ;;
    esac
done

if $HELP; then
    cat <<'EOF'
dag-utilization — DAG subagent utilization report

USAGE:
  dag-utilization [OPTIONS]

OPTIONS:
  --lookback N       Lookback window in minutes (default: 1440 = 24h)
  --json             Output structured JSON instead of colored table
  --role ROLE        Filter to specific role(s). Repeatable.
                     (e.g. --role explore --role implementor)
  --failures-only    Show only failed/suboptimal results
  -h, --help         Show this help

EXIT CODES:
  0  Healthy — all intended roles dispatched successfully
  1  Warning — deviations from intended config or sub-100% success
  2  Critical — jq missing, or actual failures (non-cancelled) in window

DESCRIPTION:
  Reads ~/.grok/logs/unified.jsonl for subagent spawn, completion, and
  failure events within the lookback window. Compares actual model usage
  against the active DAG config (~/.grok/dag-mode → preset .toml file).

  Cancelled subagents are excluded from success-rate calculations.
  The orchestrator role is excluded from "never dispatched" checks.

EXAMPLES:
  dag-utilization                           # last 24h, human-readable
  dag-utilization --lookback 60 --json      # last 1h, JSON
  dag-utilization --role plan               # plan role only
  dag-utilization --failures-only           # only problems
EOF
    exit 0
fi

# ---------------------------------------------------------------------------
# Determine active DAG preset
# ---------------------------------------------------------------------------
DAG_LABEL="unknown"
PRESET_FILE=""

if [[ -f "$DAG_MODE_FILE" ]]; then
    DAG_LABEL=$(head -1 "$DAG_MODE_FILE" | tr -d '[:space:]')
fi

# Map label to preset file
case "$DAG_LABEL" in
    full|max|flagship|best)    PRESET_FILE="$PRESETS_DIR/full-dag.toml" ;;
    economy|cheap|daily|cost)  PRESET_FILE="$PRESETS_DIR/economy-dag.toml" ;;
    mixed|diverse|multi-family|ensemble|cross) PRESET_FILE="$PRESETS_DIR/mixed-dag.toml" ;;
    *)                         PRESET_FILE="$PRESETS_DIR/full-dag.toml"
                               DAG_LABEL="full (fallback)" ;;
esac

if [[ ! -f "$PRESET_FILE" ]]; then
    echo "WARNING: DAG preset file not found: $PRESET_FILE" >&2
    PRESET_FILE=""
fi

# ---------------------------------------------------------------------------
# Parse TOML: extract [subagents.models] and [subagents.fallback]
# Output: "role:model:priority" lines (one per entry)
# priority is "primary" or "fallback"
# ---------------------------------------------------------------------------
parse_toml_section() {
    local file="$1"
    local section="$2"
    local priority="$3"
    local in_section=false

    while IFS= read -r line; do
        # Start of target section
        if [[ "$line" =~ ^\[${section}\]$ ]]; then
            in_section=true
            continue
        fi
        # Next section header — stop
        if $in_section && [[ "$line" =~ ^\[.*\]$ ]]; then
            break
        fi
        # Parse role = "model" lines
        if $in_section && [[ "$line" =~ ^[[:space:]]*([a-z][a-z-]*)[[:space:]]*=[[:space:]]*\"(.+)\"[[:space:]]*$ ]]; then
            printf '%s:%s:%s\n' "${BASH_REMATCH[1]}" "${BASH_REMATCH[2]}" "$priority"
        fi
    done < "$file"
}

# Build intended config as a temp file of "role:model:priority" lines
INTENDED_CONFIG_FILE=$(mktemp -t dag-util-intended.XXXXXX)
trap 'rm -f "$INTENDED_CONFIG_FILE" "$SPAWNS_FILE" "$TERMINAL_FILE" 2>/dev/null || true' EXIT

if [[ -n "$PRESET_FILE" && -f "$PRESET_FILE" ]]; then
    parse_toml_section "$PRESET_FILE" "subagents.models" "primary" >> "$INTENDED_CONFIG_FILE"
    parse_toml_section "$PRESET_FILE" "subagents.fallback" "fallback" >> "$INTENDED_CONFIG_FILE"
fi

# ---------------------------------------------------------------------------
# Extract subagent events from log within the lookback window
# ---------------------------------------------------------------------------
CUTOFF_EPOCH=$(cutoff_epoch "$LOOKBACK")

if [[ ! -f "$LOG_FILE" ]]; then
    echo "WARNING: log file not found: $LOG_FILE" >&2
    # Proceed with empty data
fi

# We use a two-pass approach with jq:
# 1. Extract all subagent spawn events → subagent_id, role, model, parent_model
# 2. Extract all terminal events (completed + failed) → subagent_id, success, cancelled, duration_ms, turns, tool_calls, error
#
# Timestamps in JSON are ISO-8601: "2026-08-02T04:45:15.025Z"
# We filter by comparing the date portion against the cutoff.

CUTOFF_TS=$(date -u -r "$CUTOFF_EPOCH" '+%Y-%m-%dT%H:%M:%S' 2>/dev/null || echo "")

SPAWNS_FILE=$(mktemp -t dag-util-spawns.XXXXXX)
TERMINAL_FILE=$(mktemp -t dag-util-terminal.XXXXXX)

if [[ -f "$LOG_FILE" && -n "$CUTOFF_TS" ]]; then
    # Extract spawn events
    jq -r --arg cutoff "$CUTOFF_TS" '
        select(.ts >= $cutoff and .msg == "subagent spawn credentials")
        | [.ts, .ctx.subagent_id, .ctx.subagent_type, .ctx.effective_model, .ctx.parent_model]
        | @tsv
    ' "$LOG_FILE" 2>/dev/null > "$SPAWNS_FILE" || true

    # Extract terminal events (completed + failed)
    jq -r --arg cutoff "$CUTOFF_TS" '
        select(.ts >= $cutoff and (.msg == "subagent completed" or .msg == "subagent failed"))
        | [.ts, .msg, .ctx.subagent_id, .ctx.subagent_type, .ctx.effective_model,
           .ctx.success, .ctx.cancelled, .ctx.duration_ms, .ctx.turns, .ctx.tool_calls, .ctx.error // ""]
        | @tsv
    ' "$LOG_FILE" 2>/dev/null > "$TERMINAL_FILE" || true
fi

# ---------------------------------------------------------------------------
# Aggregate per-subagent: for each spawn, find its terminal event
# A subagent can have:
#   - spawn + completed (success=true)  → success
#   - spawn + failed (cancelled=true)   → cancelled (exclude from rate)
#   - spawn + failed (cancelled=false)  → real failure
#   - spawn only (no terminal)          → in-flight (exclude from rate)
#
# We build per-role counters using temp files.
# ---------------------------------------------------------------------------

# Read terminal events into a lookup: subagent_id → outcome
# Format: subagent_id<TAB>outcome<TAB>details
# outcome: success|failure|cancelled|none
TERMINAL_LOOKUP=$(mktemp -t dag-util-tlookup.XXXXXX)
if [[ -f "$TERMINAL_FILE" ]]; then
    # For each subagent_id, collect terminal events
    # We use awk to pick the appropriate terminal event per subagent_id.
    # Priority: completed > failed(cancelled=false) > failed(cancelled=true)
    awk -F'\t' '
    {
        ts = $1; msg = $2; sid = $3; role = $4; model = $5;
        success = $6; cancelled = $7; duration = $8; turns = $9; tool_calls = $10;
        err = $11;

        # Build outcome key: completed=1, failed+!cancelled=2, failed+cancelled=3
        if (msg == "subagent completed") {
            key = 1;
        } else if (cancelled == "true") {
            key = 3;
        } else {
            key = 2;
        }

        # Keep the best (lowest-numbered) outcome per subagent_id
        if (!(sid in best_key) || key < best_key[sid]) {
            best_key[sid] = key;
            best_role[sid] = role;
            best_model[sid] = model;
            best_success[sid] = success;
            best_cancelled[sid] = cancelled;
            best_duration[sid] = duration;
            best_turns[sid] = turns;
            best_tool_calls[sid] = tool_calls;
            best_err[sid] = err;
        }
    }
    END {
        for (sid in best_key) {
            printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n",
                   sid, best_role[sid], best_model[sid],
                   best_success[sid], best_cancelled[sid],
                   best_duration[sid], best_turns[sid], best_tool_calls[sid],
                   best_err[sid];
        }
    }
    ' "$TERMINAL_FILE" > "$TERMINAL_LOOKUP"
fi

# Now iterate spawns and match against terminal outcomes
# Per-role counters (using separate files since bash 3.2 has no associative arrays)
ROLES_DIR=$(mktemp -d -t dag-util-roles.XXXXXX)

# Initialize counters function
role_file() { echo "$ROLES_DIR/${1}.txt"; }
role_init() {
    local r="$1"
    local f
    f=$(role_file "$r")
    if [[ ! -f "$f" ]]; then
        printf 'total=0\nsuccess=0\nfailure=0\ncancelled=0\nin_flight=0\ntotal_duration_ms=0\ntotal_turns=0\ntotal_tool_calls=0\n' > "$f"
    fi
}
role_increment() {
    local r="$1" field="$2" val="$3"
    local f
    f=$(role_file "$r")
    role_init "$r"

    if [[ "$field" == "models" ]]; then
        # Append model; deduplication handled at read time
        printf 'models=%s\n' "$val" >> "$f"
    else
        local cur
        cur=$(grep "^${field}=" "$f" | cut -d= -f2- || echo "0")
        local new=$(( cur + val ))
        sed -i '' "s/^${field}=.*/${field}=${new}/" "$f"
    fi
}
role_get() {
    local r="$1" field="$2"
    local f
    f=$(role_file "$r")
    if [[ -f "$f" ]]; then
        grep "^${field}=" "$f" | cut -d= -f2- || echo "0"
    else
        echo "0"
    fi
}
role_models() {
    local r="$1"
    local f
    f=$(role_file "$r")
    if [[ -f "$f" ]]; then
        grep "^models=" "$f" 2>/dev/null | sed 's/^models=//' | grep -v '^$' || true
    fi
}

# Model usage counter (global)
MODEL_USAGE_FILE=$(mktemp -t dag-util-musage.XXXXXX)

if [[ -f "$SPAWNS_FILE" ]]; then
    while IFS=$'\t' read -r ts sid role model parent_model; do
        # Apply role filter if specified
        if [[ -n "$ROLE_FILTERS" ]]; then
            if ! echo "$ROLE_FILTERS" | grep -qxF "$role"; then
                continue
            fi
        fi

        # Count this spawn
        role_increment "$role" "total" 1

        # Track model usage (global + per-role)
        printf '%s\t%s\n' "$model" "$role" >> "$MODEL_USAGE_FILE"
        role_increment "$role" "models" "$model"

        # Look up terminal outcome
        outcome=""
        outcome=$(awk -F'\t' -v sid="$sid" '$1 == sid {print $4","$5","$6","$7","$8","$9}' "$TERMINAL_LOOKUP" 2>/dev/null || echo "")

        if [[ -z "$outcome" ]]; then
            # No terminal event yet → in-flight
            role_increment "$role" "in_flight" 1
        else
            o_success=""
            o_cancelled=""
            o_dur=""
            o_turns=""
            o_tc=""
            o_success=$(echo "$outcome" | cut -d, -f1)
            o_cancelled=$(echo "$outcome" | cut -d, -f2)
            o_dur=$(echo "$outcome" | cut -d, -f3)
            o_turns=$(echo "$outcome" | cut -d, -f4)
            o_tc=$(echo "$outcome" | cut -d, -f5)

            if [[ "$o_cancelled" == "true" ]]; then
                role_increment "$role" "cancelled" 1
            elif [[ "$o_success" == "true" ]]; then
                role_increment "$role" "success" 1
                role_increment "$role" "total_duration_ms" "$o_dur"
                role_increment "$role" "total_turns" "$o_turns"
                role_increment "$role" "total_tool_calls" "$o_tc"
            else
                role_increment "$role" "failure" 1
                role_increment "$role" "total_duration_ms" "$o_dur"
                role_increment "$role" "total_turns" "$o_turns"
                role_increment "$role" "total_tool_calls" "$o_tc"
            fi
        fi
    done < "$SPAWNS_FILE"
fi

# Collect unique roles from spawns
ALL_ROLES=$(ls "$ROLES_DIR"/*.txt 2>/dev/null | sed 's|.*/||; s|\.txt$||' | sort -u || true)

# ---------------------------------------------------------------------------
# Compute intended model per role (from config)
# For each role, the intended model is the primary entry.
# ---------------------------------------------------------------------------
intended_model_for_role() {
    local role="$1"
    if [[ -f "$INTENDED_CONFIG_FILE" ]]; then
        grep "^${role}:" "$INTENDED_CONFIG_FILE" | grep ':primary$' | head -1 | cut -d: -f2 || true
    fi
}

intended_fallback_for_role() {
    local role="$1"
    if [[ -f "$INTENDED_CONFIG_FILE" ]]; then
        grep "^${role}:" "$INTENDED_CONFIG_FILE" | grep ':fallback$' | head -1 | cut -d: -f2 || true
    fi
}

# ---------------------------------------------------------------------------
# Compute deviations: where actual model ≠ intended primary model
# ---------------------------------------------------------------------------
compute_deviations() {
    local tmp
    tmp=$(mktemp -t dag-util-devs.XXXXXX)

    for role in $ALL_ROLES; do
        local intended fallback
        intended=$(intended_model_for_role "$role")
        fallback=$(intended_fallback_for_role "$role")

        local used_models
        used_models=$(role_models "$role" | sort -u)

        for model in $used_models; do
            [[ -z "$model" ]] && continue
            local dev_type=""

            if [[ -n "$intended" && "$model" == "$intended" ]]; then
                dev_type="intended"
            elif [[ -n "$fallback" && "$model" == "$fallback" ]]; then
                dev_type="fallback"
            else
                dev_type="unexpected"
            fi

            printf '%s\t%s\t%s\t%s\t%s\n' "$role" "$model" "$dev_type" "${intended:-none}" "${fallback:-none}" >> "$tmp"
        done
    done
    cat "$tmp"
    rm -f "$tmp"
}

# ---------------------------------------------------------------------------
# Collect "never dispatched" roles: in config but not in actual spawns
# ---------------------------------------------------------------------------
never_dispatched_roles() {
    if [[ ! -f "$INTENDED_CONFIG_FILE" ]]; then
        return
    fi
    local configured_roles
    configured_roles=$(cut -d: -f1 "$INTENDED_CONFIG_FILE" | sort -u)

    for role in $configured_roles; do
        # Skip orchestrator from "never dispatched" check
        [[ "$role" == "orchestrator" ]] && continue

        # If role filters are active, only check roles in the filter set
        if [[ -n "$ROLE_FILTERS" ]]; then
            if ! echo "$ROLE_FILTERS" | grep -qxF "$role"; then
                continue
            fi
        fi

        if ! echo "$ALL_ROLES" | grep -qxF "$role" 2>/dev/null; then
            echo "$role"
        fi
    done
}

# ---------------------------------------------------------------------------
# Is output a terminal? (for color detection)
# ---------------------------------------------------------------------------
if [[ -t 1 ]]; then
    C_GREEN='\033[0;32m'
    C_RED='\033[0;31m'
    C_YELLOW='\033[0;33m'
    C_BOLD='\033[1m'
    C_RESET='\033[0m'
    C_CYAN='\033[0;36m'
else
    C_GREEN='' C_RED='' C_YELLOW='' C_BOLD='' C_RESET='' C_CYAN=''
fi

# ---------------------------------------------------------------------------
# Symbol for success rate
# ---------------------------------------------------------------------------
symbol() {
    local rate="$1"
    if [[ "$rate" -ge 100 ]]; then
        printf "${C_GREEN}✓${C_RESET}"
    elif [[ "$rate" -ge 50 ]]; then
        printf "${C_YELLOW}⚠${C_RESET}"
    else
        printf "${C_RED}✗${C_RESET}"
    fi
}

# ---------------------------------------------------------------------------
# Determine exit code
# ---------------------------------------------------------------------------
EXIT_CODE=0

check_exit_code() {
    local total_spawns=0
    local has_failures=false
    local has_deviations=false
    local has_never_dispatched=false

    for role in $ALL_ROLES; do
        local f t
        f=$(role_get "$role" "failure")
        t=$(role_get "$role" "total")
        total_spawns=$(( total_spawns + t ))
        [[ "${f:-0}" -gt 0 ]] && has_failures=true
    done

    # Zero activity → healthy, not a failure
    if [[ $total_spawns -eq 0 ]]; then
        EXIT_CODE=0
        return
    fi

    if [[ -f "$INTENDED_CONFIG_FILE" ]]; then
        DEVIATIONS=$(compute_deviations)
        if echo "$DEVIATIONS" | grep -q 'fallback\|unexpected' 2>/dev/null; then
            has_deviations=true
        fi
        local nd
        nd=$(never_dispatched_roles)
        [[ -n "$nd" ]] && has_never_dispatched=true
    fi

    if $has_failures; then
        EXIT_CODE=2
    elif $has_deviations || $has_never_dispatched; then
        EXIT_CODE=1
    else
        EXIT_CODE=0
    fi
}

# ---------------------------------------------------------------------------
# JSON output
# ---------------------------------------------------------------------------
output_json() {
    local total_spawns=0 total_success=0 total_failure=0 total_cancelled=0 total_inflight=0

    for role in $ALL_ROLES; do
        (( total_spawns += $(role_get "$role" "total") ))
        (( total_success += $(role_get "$role" "success") ))
        (( total_failure += $(role_get "$role" "failure") ))
        (( total_cancelled += $(role_get "$role" "cancelled") ))
        (( total_inflight += $(role_get "$role" "in_flight") ))
    done

    local evaluable=$(( total_spawns - total_cancelled - total_inflight ))
    local overall_success_rate=100
    if [[ $evaluable -gt 0 ]]; then
        overall_success_rate=$(awk "BEGIN { printf \"%.1f\", ($total_success / $evaluable) * 100 }")
    fi

    echo '{'
    printf '  "report": {\n'
    printf '    "generated": "%s",\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    printf '    "lookback_minutes": %d,\n' "$LOOKBACK"
    printf '    "log_file": "%s",\n' "$LOG_FILE"
    printf '    "active_dag_label": "%s",\n' "$DAG_LABEL"
    printf '    "config_file": "%s",\n' "${PRESET_FILE:-none}"
    printf '    "total_subagents": %d,\n' "$total_spawns"
    printf '    "total_success": %d,\n' "$total_success"
    printf '    "total_failure": %d,\n' "$total_failure"
    printf '    "total_cancelled": %d,\n' "$total_cancelled"
    printf '    "total_in_flight": %d,\n' "$total_inflight"
    printf '    "overall_success_rate_pct": %s\n' "$overall_success_rate"
    printf '  },\n'

    # intended_config — group by role with primary/fallback
    printf '  "intended_config": {\n'
    if [[ -f "$INTENDED_CONFIG_FILE" ]]; then
        # Build grouped config in a temp file
        local cfg_tmp
        cfg_tmp=$(mktemp -t dag-util-cfg.XXXXXX)
        awk -F: '{
            role=$1; model=$2; priority=$3;
            if (priority == "primary") prim[role]=model;
            else if (priority == "fallback") fall[role]=model;
        }
        END {
            for (role in prim) {
                f = (role in fall ? fall[role] : "none");
                printf "%s\034%s\034%s\n", role, prim[role], f;
            }
        }' "$INTENDED_CONFIG_FILE" > "$cfg_tmp"

        local first_cfg=true
        while IFS=$'\034' read -r role prim fall; do
            [[ -z "$role" ]] && continue
            $first_cfg || printf ',\n'
            first_cfg=false
            printf '    "%s": {"primary": "%s", "fallback": "%s"}' "$role" "$prim" "$fall"
        done < "$cfg_tmp"
        rm -f "$cfg_tmp"
        echo
    fi
    printf '  },\n'

    # roles
    printf '  "roles": {\n'
    local first_role=true
    for role in $ALL_ROLES; do
        $first_role || printf ',\n'
        first_role=false

        local t s f c i d turns tc
        t=$(role_get "$role" "total")
        s=$(role_get "$role" "success")
        f=$(role_get "$role" "failure")
        c=$(role_get "$role" "cancelled")
        i=$(role_get "$role" "in_flight")
        d=$(role_get "$role" "total_duration_ms")
        turns=$(role_get "$role" "total_turns")
        tc=$(role_get "$role" "total_tool_calls")

        local ev=$(( t - c - i ))
        local rate=100
        if [[ $ev -gt 0 ]]; then
            rate=$(awk "BEGIN { printf \"%.1f\", ($s / $ev) * 100 }")
        fi

        local avg_dur=0 avg_turns=0 avg_tc=0
        local completed=$(( s + f ))
        if [[ $completed -gt 0 ]]; then
            avg_dur=$(awk "BEGIN { printf \"%.0f\", $d / $completed }")
            avg_turns=$(awk "BEGIN { printf \"%.1f\", $turns / $completed }")
            avg_tc=$(awk "BEGIN { printf \"%.0f\", $tc / $completed }")
        fi

        local models_json=""
        local first_m=true
        for model in $(role_models "$role" | sort -u); do
            [[ -z "$model" ]] && continue
            $first_m || models_json="${models_json}, "
            first_m=false
            models_json="${models_json}\"$model\""
        done

        printf '    "%s": {\n' "$role"
        printf '      "total": %d,\n' "$t"
        printf '      "success": %d,\n' "$s"
        printf '      "failure": %d,\n' "$f"
        printf '      "cancelled": %d,\n' "$c"
        printf '      "in_flight": %d,\n' "$i"
        printf '      "success_rate_pct": %s,\n' "$rate"
        printf '      "avg_duration_ms": %s,\n' "$avg_dur"
        printf '      "avg_turns": %s,\n' "$avg_turns"
        printf '      "avg_tool_calls": %s,\n' "$avg_tc"
        printf '      "models_used": [%s]\n' "$models_json"
        printf '    }'
    done
    echo
    printf '  },\n'

    # deviations
    echo '  "deviations": ['
    local first_dev=true
    while IFS=$'\t' read -r role model dev_type intended fallback; do
        [[ "$dev_type" == "intended" ]] && continue
        $first_dev || printf ',\n'
        first_dev=false
        printf '    {"role": "%s", "actual_model": "%s", "deviation_type": "%s", "intended_model": "%s", "fallback_model": "%s"}' \
               "$role" "$model" "$dev_type" "$intended" "$fallback"
    done <<< "$(compute_deviations)"
    echo
    echo '  ],'

    # never_dispatched
    echo '  "never_dispatched_roles": ['
    local first_nd=true
    for role in $(never_dispatched_roles); do
        $first_nd || printf ',\n'
        first_nd=false
        printf '    "%s"' "$role"
    done
    echo
    echo '  ],'

    # model_usage
    echo '  "model_usage": {'
    if [[ -f "$MODEL_USAGE_FILE" ]]; then
        local first_mu=true
        sort "$MODEL_USAGE_FILE" | awk -F'\t' '{print $1}' | sort | uniq -c | sort -rn | while read -r count model; do
            $first_mu || printf ',\n'
            first_mu=false
            printf '    "%s": %d' "$model" "$count"
        done
    fi
    echo
    echo '  }'
    echo '}'
}

# ---------------------------------------------------------------------------
# Human-readable output
# ---------------------------------------------------------------------------
output_human() {
    local total_spawns=0 total_success=0 total_failure=0 total_cancelled=0 total_inflight=0

    for role in $ALL_ROLES; do
        (( total_spawns += $(role_get "$role" "total") ))
        (( total_success += $(role_get "$role" "success") ))
        (( total_failure += $(role_get "$role" "failure") ))
        (( total_cancelled += $(role_get "$role" "cancelled") ))
        (( total_inflight += $(role_get "$role" "in_flight") ))
    done

    local evaluable=$(( total_spawns - total_cancelled - total_inflight ))
    local overall_success_rate=100
    if [[ $evaluable -gt 0 ]]; then
        overall_success_rate=$(awk "BEGIN { printf \"%.1f\", ($total_success / $evaluable) * 100 }")
    fi

    # Header
    echo "════════════════════════════════════════════════════════════════"
    printf "${C_BOLD}DAG Subagent Utilization Report${C_RESET}\n"
    echo "────────────────────────────────────────────────────────────────"
    printf "  DAG label:    ${C_CYAN}%s${C_RESET}\n" "$DAG_LABEL"
    printf "  Config file:  %s\n" "${PRESET_FILE:-none}"
    printf "  Lookback:     %d minutes (%s)\n" "$LOOKBACK" "$(date -u -r "$CUTOFF_EPOCH" '+%Y-%m-%d %H:%M:%S UTC')"
    printf "  Subagents:    %d total  |  %d success  |  %d failed  |  %d cancelled  |  %d in-flight\n" \
           "$total_spawns" "$total_success" "$total_failure" "$total_cancelled" "$total_inflight"
    printf "  Overall rate: %s%%\n" "$overall_success_rate"
    echo "════════════════════════════════════════════════════════════════"
    echo ""

    if [[ $total_spawns -eq 0 ]]; then
        printf "${C_YELLOW}No subagent activity in the lookback window.${C_RESET}\n"
        return
    fi

    # Per-role summary table
    printf "${C_BOLD}%-18s %6s %6s %6s %6s %7s %7s %6s  %s${C_RESET}\n" \
           "ROLE" "TOTAL" "OK" "FAIL" "CANC" "IN-FLT" "RATE" "AVG(ms)" "MODELS"
    echo "───────────────────────────────────────────────────────────────────────────────────────"

    for role in $ALL_ROLES; do
        local t s f c i d turns tc
        t=$(role_get "$role" "total")
        s=$(role_get "$role" "success")
        f=$(role_get "$role" "failure")
        c=$(role_get "$role" "cancelled")
        i=$(role_get "$role" "in_flight")
        d=$(role_get "$role" "total_duration_ms")
        turns=$(role_get "$role" "total_turns")
        tc=$(role_get "$role" "total_tool_calls")

        local ev=$(( t - c - i ))
        local rate=100
        if [[ $ev -gt 0 ]]; then
            rate=$(awk "BEGIN { printf \"%.0f\", ($s / $ev) * 100 }")
        fi

        local avg_dur=0
        local completed=$(( s + f ))
        if [[ $completed -gt 0 ]]; then
            avg_dur=$(awk "BEGIN { printf \"%.0f\", $d / $completed }")
        fi

        local sym
        sym=$(symbol "$rate")

        # Collect models used (compact)
        local models_used
        models_used=$(role_models "$role" | sort -u | tr '\n' ' ' | sed 's/ *$//')

        # If --failures-only, skip roles with 100% success and no failures
        if $FAILURES_ONLY; then
            [[ "$f" -eq 0 && "$rate" -ge 100 ]] && continue
        fi

        # Color the rate
        local rate_color
        if [[ "$rate" -ge 100 ]]; then
            rate_color="${C_GREEN}${rate}%%${C_RESET}"
        elif [[ "$rate" -ge 50 ]]; then
            rate_color="${C_YELLOW}${rate}%%${C_RESET}"
        else
            rate_color="${C_RED}${rate}%%${C_RESET}"
        fi

        printf "%-18s %6d %6d " "$role" "$t" "$s"
        if [[ "$f" -gt 0 ]]; then
            printf "${C_RED}%6d${C_RESET} " "$f"
        else
            printf "%6d " "$f"
        fi
        printf "%6d %6d %s %7s ${C_CYAN}%s${C_RESET}\n" \
               "$c" "$i" "$sym" "${avg_dur}ms" "${models_used:-(none)}"
    done

    echo ""

    # Deviations section
    deviations=""
    deviations=$(compute_deviations)
    dev_count=""
    dev_count=$(echo "$deviations" | grep -v '^$' | grep -c 'fallback\|unexpected' 2>/dev/null || true)
    dev_count=${dev_count:-0}

    if [[ "$dev_count" -gt 0 ]]; then
        printf "${C_BOLD}%s${C_RESET}\n" "DEVIATIONS FROM INTENDED CONFIG"
        echo "────────────────────────────────────────────────────────────────"
        printf "  ${C_BOLD}%-15s %-22s %-15s %-22s${C_RESET}\n" "ROLE" "ACTUAL MODEL" "TYPE" "INTENDED MODEL"
        echo "  ─────────────────────────────────────────────────────────────────────"

        while IFS=$'\t' read -r role model dev_type intended fallback; do
            [[ "$dev_type" == "intended" ]] && continue
            local dev_label
            case "$dev_type" in
                fallback)   dev_label="${C_YELLOW}fallback${C_RESET}" ;;
                unexpected) dev_label="${C_RED}unexpected${C_RESET}" ;;
                *)          dev_label="$dev_type" ;;
            esac
            printf "  %-15s %-22s %b %-22s\n" "$role" "$model" "$dev_label" "$intended"
        done <<< "$deviations"
        echo ""
    fi

    # Never-dispatched roles
    local nd
    nd=$(never_dispatched_roles)
    if [[ -n "$nd" ]]; then
        printf "${C_YELLOW}%s${C_RESET}\n" "NEVER DISPATCHED (configured but unused in window)"
        echo "────────────────────────────────────────────────────────────────"
        for role in $nd; do
            local im
            im=$(intended_model_for_role "$role")
            printf "  ${C_YELLOW}⚠${C_RESET} %-15s → intended: %s\n" "$role" "${im:-?}"
        done
        echo ""
    fi

    # Model usage breakdown
    echo "${C_BOLD}MODEL USAGE BREAKDOWN${C_RESET}"
    echo "────────────────────────────────────────────────────────────────"
    if [[ -f "$MODEL_USAGE_FILE" ]]; then
        printf "  ${C_BOLD}%-30s %8s${C_RESET}\n" "MODEL" "CALLS"
        sort "$MODEL_USAGE_FILE" | awk -F'\t' '{print $1}' | sort | uniq -c | sort -rn | while read -r count model; do
            printf "  %-30s ${C_CYAN}%8d${C_RESET}\n" "$model" "$count"
        done
    else
        printf "  (none)\n"
    fi
    echo ""

    # Health summary
    echo "════════════════════════════════════════════════════════════════"
    printf "${C_BOLD}HEALTH SUMMARY${C_RESET}\n"
    if [[ $EXIT_CODE -eq 0 ]]; then
        printf "  ${C_GREEN}✓ Healthy${C_RESET} — all dispatched roles successful, model routing matches config\n"
    elif [[ $EXIT_CODE -eq 1 ]]; then
        printf "  ${C_YELLOW}⚠ Warning${C_RESET} — deviations from intended config or sub-100%% success rate\n"
    else
        printf "  ${C_RED}✗ Critical${C_RESET} — actual subagent failures in the window (non-cancelled)\n"
    fi
    echo "════════════════════════════════════════════════════════════════"
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
check_exit_code

if $OUTPUT_JSON; then
    output_json
else
    output_human
fi

exit $EXIT_CODE
