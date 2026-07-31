# Fixes Applied (2026-07-31)

All fixes were verified by an independent read-only review before this
document was written.

## Fix 1 — Sync the rollback preset with the live config

**Files:** `~/.grok/config-presets/best-value-dag.toml`, `~/.grok/config.toml`

The preset's model matrix (all 14 primary + fallback slots) already matched,
but its provider auth settings were stale (pre-auth-fix), so restoring it as a
rollback would have reintroduced the morning's 400s.

- `claude-opus-5`: `anthropic-version` moved out of `env_http_headers` (where
  it was silently dropped) into `extra_headers = { "anthropic-version" =
  "2023-06-01" }`; `env_http_headers` is now just `x-api-key`;
  `api_backend = "messages"`.
- `gpt-5.6-sol` / `gpt-5.6-luna`: added `api_backend = "responses"`.
- DeepSeek blocks verified unchanged (`env_key = ["DEEPSEEK_API_KEY"]`,
  base URL `https://api.deepseek.com/v1`).

After the edit, all five provider blocks are byte-identical between the two
files for `model`, `base_url`, `env_key`, `api_backend`, `extra_headers`, and
`env_http_headers`.

## Fix 2 — Rewrite `~/.grok/tools/dag-health.sh`

### Defect A — script death under `set -u`

The state-file loop read `<sig> <epoch>` lines and fed the epoch straight into
`$(( NOW_EPOCH - e ))`. On a malformed line (legacy format, or a signature
containing spaces from a JSON blob), `e` held non-numeric text, and bash
recursively evaluated it as a variable name → `logfail: unbound variable` →
the script died mid-run, silently skipping the remaining checks.

Fix: state lines are now guarded (empty lines and lines containing whitespace
are pruned) before any evaluation; no arithmetic is performed on file-derived
input. Writes are atomic (`tmp` + `mv`) using `printf '%s'` (no `%b` escape
expansion), so the state file can no longer corrupt itself.

### Defect B — 2-minute nag loop

The dedupe path deleted the signature from the state file on a hit, so a
persistent problem re-alerted every other run (observed: ALERT → dedupe →
ALERT → dedupe) instead of the documented 30-minute re-nag.

### New notification behavior (requested)

Replaced timestamp-based dedupe with **dismissal-based** behavior:

- On detection, the watcher shows a **persistent on-screen alert**
  (`osascript` `display alert ... as critical` — modal; stays on screen until
  the user closes it).
- Once closed, that problem class is recorded in the state file
  (`~/.grok/logs/dag-health.last`, one whitespace-free signature per line) and
  **never nags again**.
- Signatures are class-stable and timestamp-free: `envkey:<KEY>`,
  `logfail:<kind>` (kind normalized, e.g. `inference_failed`), `sess`.
  A genuinely new problem class still alerts; acknowledged ones stay silent.
- Dismissal is recorded only after the dialog returns successfully. If
  osascript fails (no GUI session), nothing is marked dismissed and the next
  run retries.
- Message text is sanitized (quotes/backslashes stripped) and passed to
  osascript via `argv`, so log content cannot break the AppleScript.
- While the dialog is open, the script blocks; launchd's `StartInterval`
  does not start an overlapping run, so dialogs never stack.

Reset (re-enable alerts for dismissed classes):

```sh
: > ~/.grok/logs/dag-health.last
```

Detection checks are unchanged: TUI process env keys, a 15-minute lookback
over the session log for `inference_failed` / Authentication failures /
Unauthorized (401), and SessionToken-on-claude/gpt resolutions.

### Log rotation design (architect contribution)

`~/.grok/logs/dag-health.log` grows unbounded; launchd opens it with O_APPEND
per spawn. Proposed rotation (keeps the same inode so the inherited fd stays
valid, ~1 MB cap, runs at script top before any output):

```bash
if [ -f "$LOG_DIR/dag-health.log" ] && \
   [ "$(wc -c < "$LOG_DIR/dag-health.log")" -gt 1048576 ]; then
  tail -c 1048576 "$LOG_DIR/dag-health.log" > "$LOG_DIR/.dag-health.rotate.$$" \
    && cat "$LOG_DIR/.dag-health.rotate.$$" > "$LOG_DIR/dag-health.log"
  rm -f "$LOG_DIR/.dag-health.rotate.$$"
fi
```

(Not yet applied as of this writing — pending decision.)

## Fix 3 — Config comment label

**File:** `~/.grok/config.toml` — the matrix header comment said "hardened v2"
while the matrix is hardened v3. Corrected to "hardened v3" (comment only; no
functional values touched). Same correction applied to the preset header.

## Fix 4 — Documentation

**File:** `~/Agents.md` — the "DAG health watcher" bullet updated to describe
the new behavior: persistent critical alert until closed, no re-nag after
dismissal, state-file location, and the reset command.
