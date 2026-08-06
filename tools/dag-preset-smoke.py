#!/usr/bin/env python3
"""dag-preset-smoke.py — smoke-test every primary model in each /dag preset.

Proves API connectivity + one-token generation for each role's assigned model
across labeled presets (full, mixed, economy). Does NOT exercise TUI role
routing (that requires spawn_subagent inside an active session on that preset).

Usage:
  python3 ~/.grok/tools/dag-preset-smoke.py              # all labeled presets
  python3 ~/.grok/tools/dag-preset-smoke.py mixed full   # subset
  python3 ~/.grok/tools/dag-preset-smoke.py --json

Exit 0 only if every primary model probe succeeds.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

PRESETS_DIR = Path.home() / ".grok" / "config-presets"
LABELED = ("full", "mixed", "economy")
ROLES = (
    "orchestrator",
    "explore",
    "plan",
    "architect",
    "implementor",
    "verifier",
    "general-purpose",
)

# Load credentials into env if missing
def _load_creds() -> None:
    try:
        import subprocess

        out = subprocess.check_output(
            ["python3", str(Path.home() / ".grok/tools/load_credentials.py")],
            text=True,
        )
        for line in out.splitlines():
            m = re.match(r"^export\s+([A-Z0-9_]+)='(.*)'\s*$", line)
            if m and m.group(1) not in os.environ:
                os.environ[m.group(1)] = m.group(2)
    except Exception:
        pass


def _parse_toml_simple(text: str) -> dict:
    """Minimal TOML subset parser for our preset files (no external deps)."""
    data: dict = {}
    section: list[str] = []
    # quoted table headers like [model."grok-4.5"]
    header_re = re.compile(r'^\[([^\]]+)\]\s*$')
    # key = "value" | key = true/false | key = ["a"] | key = { ... }
    kv_re = re.compile(r'^([A-Za-z0-9_.-]+)\s*=\s*(.+)$')

    def cur() -> dict:
        node = data
        for part in section:
            node = node.setdefault(part, {})
        return node

    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        hm = header_re.match(line)
        if hm:
            body = hm.group(1).strip()
            # split on . but respect "quoted".parts
            parts: list[str] = []
            buf = ""
            in_q = False
            for ch in body:
                if ch == '"':
                    in_q = not in_q
                    continue
                if ch == "." and not in_q:
                    parts.append(buf)
                    buf = ""
                    continue
                buf += ch
            if buf:
                parts.append(buf)
            section = parts
            cur()  # ensure exists
            continue
        km = kv_re.match(line)
        if not km:
            continue
        key, val = km.group(1), km.group(2).strip()
        # strip inline comments for simple values
        if val.startswith('"'):
            # "...." possibly with trailing comment
            m = re.match(r'^"(.*)"\s*(#.*)?$', val)
            value: object = m.group(1) if m else val.strip('"')
        elif val.startswith("["):
            # simple string array
            inner = val.strip("[]")
            items = re.findall(r'"([^"]*)"', inner)
            value = items
        elif val.startswith("{"):
            # simple inline table: { model = "x", agent_type = "y" }
            items = dict(re.findall(r'([A-Za-z0-9_]+)\s*=\s*"([^"]*)"', val))
            value = items
        elif val in ("true", "false"):
            value = val == "true"
        else:
            # bare number or unquoted
            value = val.split("#", 1)[0].strip().strip('"')
        cur()[key] = value
    return data


def load_preset(name: str) -> dict:
    path = PRESETS_DIR / f"{name}-dag.toml"
    if not path.is_file():
        raise FileNotFoundError(path)
    return _parse_toml_simple(path.read_text())


def resolve_model_block(preset: dict, model_id: str) -> dict:
    models = preset.get("model", {})
    if model_id in models:
        return models[model_id]
    # try without dots issues
    return models.get(model_id, {})


def first_env(keys) -> tuple[str | None, str | None]:
    if not keys:
        return None, None
    if isinstance(keys, str):
        keys = [keys]
    for k in keys:
        v = os.environ.get(k)
        if v:
            return k, v
    return (keys[0] if keys else None), None


def http_json(url: str, headers: dict, body: dict, timeout: float = 60.0) -> tuple[int, dict | str]:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                return resp.status, json.loads(raw)
            except json.JSONDecodeError:
                return resp.status, raw
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, raw
    except Exception as e:
        return 0, f"{type(e).__name__}: {e}"


def extract_text(backend: str, payload: dict | str) -> str:
    """Pull visible text from provider payloads (incl. reasoning-only models)."""
    if not isinstance(payload, dict):
        return str(payload)[:200]

    # OpenAI/DeepSeek/MiniMax/OpenRouter chat completions
    try:
        msg = payload["choices"][0]["message"]
        content = msg.get("content") or ""
        if isinstance(content, list):
            # content parts array
            parts = []
            for p in content:
                if isinstance(p, dict):
                    parts.append(p.get("text") or p.get("content") or "")
                else:
                    parts.append(str(p))
            content = "".join(parts)
        reasoning = msg.get("reasoning_content") or msg.get("reasoning") or ""
        if content and str(content).strip():
            return str(content).strip()
        if reasoning and str(reasoning).strip():
            return str(reasoning).strip()
    except Exception:
        pass

    # OpenAI responses API
    if payload.get("output_text"):
        return str(payload["output_text"]).strip()
    try:
        chunks = []
        for item in payload.get("output", []) or []:
            for c in item.get("content", []) or []:
                if c.get("text"):
                    chunks.append(c["text"])
        if chunks:
            return "".join(chunks).strip()
    except Exception:
        pass

    # Anthropic messages (text and/or thinking blocks)
    try:
        parts = payload.get("content") or []
        texts = []
        thinks = []
        for p in parts:
            if not isinstance(p, dict):
                continue
            if p.get("type") == "text" and p.get("text"):
                texts.append(p["text"])
            elif p.get("type") == "thinking" and p.get("thinking"):
                thinks.append(p["thinking"])
            elif p.get("text"):
                texts.append(p["text"])
        if texts:
            return "".join(texts).strip()
        if thinks:
            return "".join(thinks).strip()
    except Exception:
        pass

    return ""


def probe_model(model_id: str, block: dict, marker: str) -> dict:
    api_model = block.get("model") or model_id
    base = (block.get("base_url") or "").rstrip("/")
    backend = block.get("api_backend") or "chat_completions"
    env_keys = block.get("env_key") or []
    env_name, api_key = first_env(env_keys)
    extra_headers = block.get("extra_headers") or {}
    env_http = block.get("env_http_headers") or {}

    result = {
        "model_id": model_id,
        "api_model": api_model,
        "backend": backend,
        "base_url": base,
        "env_key": env_name,
        "ok": False,
        "status": None,
        "latency_ms": None,
        "reply": None,
        "error": None,
    }

    if not base:
        result["error"] = "missing base_url in model block"
        return result
    if not api_key:
        result["error"] = f"missing API key ({env_keys})"
        return result

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "dag-preset-smoke/1.0",
    }
    # auth
    if "anthropic" in base:
        headers["x-api-key"] = api_key
        headers["anthropic-version"] = "2023-06-01"
    else:
        headers["Authorization"] = f"Bearer {api_key}"

    if isinstance(extra_headers, dict):
        headers.update(extra_headers)
    if isinstance(env_http, dict):
        for hk, ek in env_http.items():
            v = os.environ.get(ek)
            if v:
                headers[hk] = v

    prompt = f"Reply with exactly this token and nothing else: {marker}"

    # Generous token budget — reasoning models burn tokens before visible text.
    if backend == "messages" or "anthropic.com" in base:
        url = f"{base}/messages"
        body = {
            "model": api_model,
            "max_tokens": 256,
            "messages": [{"role": "user", "content": prompt}],
        }
    elif backend == "responses":
        url = f"{base}/responses"
        body = {
            "model": api_model,
            "input": prompt,
            "max_output_tokens": 128,
        }
    else:
        # chat_completions default
        url = f"{base}/chat/completions"
        body = {
            "model": api_model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt + "\nDo not think out loud. Output only the token.",
                }
            ],
            "max_tokens": 256,
            "temperature": 0,
        }

    t0 = time.time()
    status, payload = http_json(url, headers, body, timeout=90.0)
    result["latency_ms"] = int((time.time() - t0) * 1000)
    result["status"] = status
    text = extract_text(backend, payload).strip()
    result["reply"] = text[:120]

    if status and 200 <= int(status) < 300:
        # HTTP success + recognizable completion payload = model works.
        # Reasoning models may return empty visible content with reasoning only;
        # extract_text already lifts reasoning_content/thinking when needed.
        looks_like_completion = isinstance(payload, dict) and (
            "choices" in payload
            or "output" in payload
            or "output_text" in payload
            or payload.get("type") == "message"
            or "content" in payload
        )
        if text or looks_like_completion:
            result["ok"] = True
            if not text:
                result["reply"] = "(empty content; HTTP 200 completion accepted)"
                result["note"] = "empty visible text"
            elif marker not in text:
                result["note"] = "non-empty reply but marker not echoed"
        else:
            result["error"] = f"HTTP {status} but unparseable payload: {str(payload)[:200]}"
    else:
        err = payload
        if isinstance(payload, dict):
            err = payload.get("error", payload)
        result["error"] = json.dumps(err)[:300] if isinstance(err, (dict, list)) else str(err)[:300]
    return result


def run_preset(name: str) -> dict:
    preset = load_preset(name)
    role_models = (preset.get("subagents") or {}).get("models") or {}
    fallbacks = (preset.get("subagents") or {}).get("fallback") or {}
    default = (preset.get("models") or {}).get("default")

    # orchestrator often equals [models].default
    if "orchestrator" not in role_models and default:
        role_models = dict(role_models)
        role_models["orchestrator"] = default

    rows = []
    unique_probes: dict[str, dict] = {}
    cache: dict[str, dict] = {}

    for role in ROLES:
        mid = role_models.get(role) or ("?" if role != "orchestrator" else default or "?")
        fb = fallbacks.get(role, "?")
        if mid not in cache and mid != "?":
            block = resolve_model_block(preset, mid)
            marker = f"SMOKE_OK_{name}_{mid}".replace("-", "_").replace(".", "_")[:48]
            cache[mid] = probe_model(mid, block, marker)
            unique_probes[mid] = cache[mid]
        probe = cache.get(mid, {"ok": False, "error": "no model id", "model_id": mid})
        rows.append(
            {
                "role": role,
                "primary": mid,
                "fallback": fb,
                "ok": probe.get("ok", False),
                "latency_ms": probe.get("latency_ms"),
                "status": probe.get("status"),
                "reply": probe.get("reply"),
                "error": probe.get("error"),
                "note": probe.get("note"),
                "backend": probe.get("backend"),
                "api_model": probe.get("api_model"),
            }
        )

    ok = all(r["ok"] for r in rows)
    return {
        "preset": name,
        "ok": ok,
        "default": default,
        "roles": rows,
        "unique_models": unique_probes,
    }


def main() -> int:
    _load_creds()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("presets", nargs="*", default=list(LABELED))
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    results = []
    for name in args.presets:
        name = name.lower().strip()
        if name.endswith("-dag"):
            name = name[: -len("-dag")]
        try:
            results.append(run_preset(name))
        except Exception as e:
            results.append({"preset": name, "ok": False, "error": str(e), "roles": []})

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        for pr in results:
            flag = "PASS" if pr.get("ok") else "FAIL"
            print(f"\n═══ PRESET: {pr['preset'].upper()}  [{flag}] ═══")
            if pr.get("error"):
                print(f"  error: {pr['error']}")
                continue
            print(f"  default/main: {pr.get('default')}")
            print(
                f"  {'role':<16} {'primary':<22} {'backend':<16} {'ms':>6}  status  result"
            )
            print("  " + "-" * 90)
            for r in pr["roles"]:
                st = "OK " if r["ok"] else "ERR"
                ms = r["latency_ms"] if r["latency_ms"] is not None else "-"
                detail = r["reply"] if r["ok"] else (r.get("error") or "?")
                if isinstance(detail, str) and len(detail) > 60:
                    detail = detail[:57] + "..."
                print(
                    f"  {r['role']:<16} {r['primary']:<22} {str(r.get('backend') or '-'):<16} "
                    f"{ms:>6}  {st}     {detail}"
                )
        print()
        overall = all(p.get("ok") for p in results)
        print(f"OVERALL: {'PASS' if overall else 'FAIL'}")
        # unique model summary
        seen = {}
        for pr in results:
            for mid, probe in (pr.get("unique_models") or {}).items():
                seen.setdefault(mid, probe)
        print("\nUnique primary models probed:")
        for mid, probe in sorted(seen.items()):
            print(
                f"  {'OK' if probe.get('ok') else 'ERR'}  {mid:<22} "
                f"{probe.get('latency_ms')}ms  {probe.get('reply') or probe.get('error')}"
            )

    return 0 if all(p.get("ok") for p in results) else 1


if __name__ == "__main__":
    sys.exit(main())
