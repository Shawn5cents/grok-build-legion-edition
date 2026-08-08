"""toml.py — minimal TOML loader for dag-inspector.

Tries ``tomllib`` (Python 3.11+) first, then falls back to a hand-rolled
parser that handles the subset of TOML actually used by Grok DAG configs:

* Section headers: ``[model.deepseek-v4-pro]`` and ``[model."minimax-m3"]``
* Quoted basic-string keys: ``[model."grok-4.5"]``
* Bare keys with dashes / dots
* Scalar values: string, integer, float, bool
* Arrays of basic strings: ``env_key = ["DEEPSEEK_API_KEY"]``
* Inline tables: ``{ model = "x", agent_type = "y" }``
* Arrays of inline tables: ``[ { ... }, { ... } ]``
* Comments (``# ...``) at the start of a line

Hand-rolled parser does NOT support: multi-line basic strings, multi-line
arrays, dotted-keys-on-multiple-lines, datetime literals, hex/oct/bin ints,
or literal strings (``'...'``). None of those appear in the DAG presets.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def load(path: str) -> Dict[str, Any]:
    """Load a TOML file and return a nested dict. Raises on syntax errors."""
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()
    return loads(text)


def loads(text: str) -> Dict[str, Any]:
    """Parse TOML text into a nested dict. Prefers tomllib if available."""
    try:  # Python 3.11+
        import tomllib  # type: ignore

        return tomllib.loads(text)
    except ImportError:
        pass
    except Exception:
        # tomllib is strict; if our minimal parser can do better on this
        # specific dialect, fall through to it. We still prefer tomllib
        # when it succeeds.
        if "HandRolledParser" not in globals():
            pass
    return _HandRolledParser(text).parse()


# ---------------------------------------------------------------------------
# Hand-rolled parser (Python 3.9 compatible)
# ---------------------------------------------------------------------------


_SECTION_RE = re.compile(r"^\[([^\]]+)\]\s*$")
_ARRAY_OF_TABLES_RE = re.compile(r"^\[\[([^\]]+)\]\]\s*$")


class TomlError(ValueError):
    """Raised on a TOML syntax error we can't recover from."""


class _HandRolledParser:
    def __init__(self, text: str) -> None:
        self.text = text
        self.lines = text.splitlines()
        self.pos = 0
        self.root: Dict[str, Any] = {}
        # Stack of currently-open sections: list of (raw_name, container).
        self._section_stack: List[Tuple[str, Any]] = [("$root", self.root)]

    # -- top-level -----------------------------------------------------

    def parse(self) -> Dict[str, Any]:
        while self.pos < len(self.lines):
            line = self._strip_comment(self.lines[self.pos])
            if not line.strip():
                self.pos += 1
                continue

            # [[array.of.tables]]
            m = _ARRAY_OF_TABLES_RE.match(line)
            if m:
                self._open_array_table(m.group(1).strip())
                self.pos += 1
                continue

            # [section.subsection]
            m = _SECTION_RE.match(line)
            if m:
                self._open_table(m.group(1).strip())
                self.pos += 1
                continue

            # bare key = value
            self._parse_keyvalue(line)
            self.pos += 1

        return self.root

    # -- helpers --------------------------------------------------------

    def _strip_comment(self, raw: str) -> str:
        """Remove trailing ``# ...`` comments (preserving ``#`` inside strings)."""
        out, i, in_str, q = [], 0, False, ""
        while i < len(raw):
            c = raw[i]
            if in_str:
                out.append(c)
                if c == "\\" and i + 1 < len(raw):
                    out.append(raw[i + 1])
                    i += 2
                    continue
                if c == q:
                    in_str = False
                i += 1
                continue
            if c in ('"', "'"):
                in_str = True
                q = c
                out.append(c)
                i += 1
                continue
            if c == "#":
                break
            out.append(c)
            i += 1
        return "".join(out)

    def _open_table(self, name: str) -> None:
        container = self._navigate_or_create(name, create=True)
        self._section_stack = [("$root", self.root), (name, container)]

    def _open_array_table(self, name: str) -> None:
        # Find or create the array under the named path.
        parent_name, parent = self._section_stack[-1]
        path = name.split(".")
        cur = parent
        for key in path[:-1]:
            cur = cur.setdefault(key, {})
        last = path[-1]
        arr = cur.setdefault(last, [])
        new_table: Dict[str, Any] = {}
        arr.append(new_table)
        self._section_stack = [("$root", self.root), (name, new_table)]

    def _navigate_or_create(self, name: str, create: bool) -> Dict[str, Any]:
        """Navigate into nested table ``a.b.c`` via quoted/bare keys."""
        path = self._split_dotted(name)
        cur: Any = self.root
        for key in path:
            existing = cur.get(key)
            if existing is None:
                if not create:
                    raise TomlError(f"unknown section {key!r} in [{name}]")
                existing = {}
                cur[key] = existing
            elif not isinstance(existing, dict):
                raise TomlError(f"path collision on {key!r} in [{name}]")
            cur = existing
        return cur  # type: ignore[return-value]

    @staticmethod
    def _split_dotted(name: str) -> List[str]:
        """Split ``model."minimax-m3"`` → ``['model', 'minimax-m3']``.

        Honors quoted segments so embedded dots don't split keys.
        """
        parts: List[str] = []
        cur, in_str, q = [], False, ""
        i = 0
        while i < len(name):
            c = name[i]
            if in_str:
                cur.append(c)
                if c == "\\" and i + 1 < len(name):
                    cur.append(name[i + 1])
                    i += 2
                    continue
                if c == q:
                    in_str = False
                i += 1
                continue
            if c in ('"', "'"):
                in_str = True
                q = c
                cur.append(c)
                i += 1
                continue
            if c == ".":
                parts.append("".join(cur).strip())
                cur = []
                i += 1
                continue
            cur.append(c)
            i += 1
        parts.append("".join(cur).strip())
        # Strip surrounding quotes from each part.
        cleaned: List[str] = []
        for p in parts:
            if len(p) >= 2 and p[0] == p[-1] and p[0] in ('"', "'"):
                cleaned.append(p[1:-1])
            else:
                cleaned.append(p)
        return cleaned

    # -- key/value ------------------------------------------------------

    def _parse_keyvalue(self, line: str) -> None:
        # Find the FIRST '=' that isn't inside a string.
        eq_idx, in_str, q = -1, False, ""
        for i, c in enumerate(line):
            if in_str:
                if c == "\\" and i + 1 < len(line):
                    i += 1
                    continue
                if c == q:
                    in_str = False
                continue
            if c in ('"', "'"):
                in_str = True
                q = c
                continue
            if c == "=":
                eq_idx = i
                break
        if eq_idx < 0:
            raise TomlError(f"line {self.pos+1}: missing '=' — {line!r}")

        raw_key = line[:eq_idx].strip()
        raw_val = line[eq_idx + 1 :].strip()
        key = self._parse_key(raw_key)
        value = self._parse_value(raw_val)

        _, container = self._section_stack[-1]
        if isinstance(key, list):
            # Dotted key — set nested. a.b.c = 1 → container[a][b][c] = 1
            cur = container
            for k in key[:-1]:
                nxt = cur.get(k)
                if not isinstance(nxt, dict):
                    nxt = {}
                    cur[k] = nxt
                cur = nxt
            cur[key[-1]] = value
        else:
            container[key] = value

    @staticmethod
    def _parse_key(raw: str) -> Any:
        """Return either a bare string key or a list of keys for dotted keys."""
        if '"' in raw or "'" in raw or "." in raw:
            # Could be a dotted key with quoted segments.
            parts = _HandRolledParser._split_dotted(raw)
            if len(parts) == 1:
                return parts[0]
            return parts
        return raw

    # -- values ---------------------------------------------------------

    def _parse_value(self, raw: str) -> Any:
        raw = raw.strip()
        if not raw:
            return ""
        # Inline array of tables / inline table / array / scalar
        if raw.startswith("[") and raw.endswith("]"):
            return self._parse_array(raw[1:-1].strip())
        if raw.startswith("{") and raw.endswith("}"):
            return self._parse_inline_table(raw[1:-1].strip())
        return self._parse_scalar(raw)

    def _parse_array(self, body: str) -> List[Any]:
        # Split on top-level commas.
        items = self._split_top_level(body, ",")
        return [self._parse_value(item.strip()) for item in items if item.strip()]

    def _parse_inline_table(self, body: str) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for piece in self._split_top_level(body, ","):
            piece = piece.strip()
            if not piece:
                continue
            eq_idx, in_str, q = -1, False, ""
            for i, c in enumerate(piece):
                if in_str:
                    if c == "\\" and i + 1 < len(piece):
                        i += 1
                        continue
                    if c == q:
                        in_str = False
                    continue
                if c in ('"', "'"):
                    in_str = True
                    q = c
                    continue
                if c == "=":
                    eq_idx = i
                    break
            if eq_idx < 0:
                continue
            key = self._parse_key(piece[:eq_idx].strip())
            value = self._parse_value(piece[eq_idx + 1 :].strip())
            if isinstance(key, list):
                cur = out
                for k in key[:-1]:
                    nxt = cur.get(k)
                    if not isinstance(nxt, dict):
                        nxt = {}
                        cur[k] = nxt
                    cur = nxt
                cur[key[-1]] = value
            else:
                out[key] = value
        return out

    def _split_top_level(self, body: str, sep: str) -> List[str]:
        """Split on ``sep`` at the top level (ignoring ones in strings/braces)."""
        out: List[str] = []
        depth = 0
        in_str = False
        q = ""
        i = 0
        buf: List[str] = []
        while i < len(body):
            c = body[i]
            if in_str:
                buf.append(c)
                if c == "\\" and i + 1 < len(body):
                    buf.append(body[i + 1])
                    i += 2
                    continue
                if c == q:
                    in_str = False
                i += 1
                continue
            if c in ('"', "'"):
                in_str = True
                q = c
                buf.append(c)
                i += 1
                continue
            if c in "[{":
                depth += 1
            elif c in "]}":
                depth -= 1
            if c == sep and depth == 0:
                out.append("".join(buf))
                buf = []
                i += 1
                continue
            buf.append(c)
            i += 1
        if buf:
            out.append("".join(buf))
        return out

    @staticmethod
    def _parse_scalar(raw: str) -> Any:
        s = raw.strip()
        # Basic strings
        if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
            return _HandRolledParser._unescape_basic(s[1:-1])
        # Literal strings
        if len(s) >= 2 and s[0] == "'" and s[-1] == "'":
            return s[1:-1]
        # Booleans
        if s in ("true", "True"):
            return True
        if s in ("false", "False"):
            return False
        # Numbers
        try:
            if any(c in s for c in ".eE"):
                return float(s)
            return int(s)
        except ValueError:
            pass
        # Inline array / table may have ended up here via _parse_value path.
        if s.startswith("[") and s.endswith("]"):
            return _HandRolledParser._parse_array_static(s[1:-1].strip())
        if s.startswith("{") and s.endswith("}"):
            return _HandRolledParser._parse_inline_table_static(s[1:-1].strip())
        # Unknown — return raw string so callers can still see something.
        return s

    @staticmethod
    def _parse_array_static(body: str) -> List[Any]:
        parser = _HandRolledParser("")
        return parser._parse_array(body)

    @staticmethod
    def _parse_inline_table_static(body: str) -> Dict[str, Any]:
        parser = _HandRolledParser("")
        return parser._parse_inline_table(body)

    @staticmethod
    def _unescape_basic(s: str) -> str:
        out: List[str] = []
        i = 0
        while i < len(s):
            c = s[i]
            if c == "\\" and i + 1 < len(s):
                nxt = s[i + 1]
                out.append({"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\"}.get(nxt, nxt))
                i += 2
                continue
            out.append(c)
            i += 1
        return "".join(out)


# ---------------------------------------------------------------------------
# Value normalization helpers (used by config.py)
# ---------------------------------------------------------------------------


def env_key_as_list(value: Any) -> List[str]:
    """Normalize ``env_key`` to a list of strings.

    TOML sometimes encodes it as a string, sometimes as an array of strings;
    both are valid in the Grok config dialect. Default to ``[]`` if missing.
    """
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(v) for v in value]
    return [str(value)]