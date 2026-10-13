"""A tiny YAML-subset reader/writer so the runner needs zero dependencies.

Supports: nested mappings, lists ("- item" and "- key: value" blocks),
inline lists [a, b], strings (quoted or bare), ints, floats, true/false, null.
Comments start with "#" at line start or after " #".
If PyYAML is installed we use it instead (it handles everything).
"""
import re

try:  # pragma: no cover - optional
    import yaml as _yaml
except ImportError:
    _yaml = None

_KV = re.compile(r"^[A-Za-z0-9_.\-]+:(\s|$)")


def loads(text):
    if _yaml is not None:
        return _yaml.safe_load(text)
    lines = []
    for raw in text.splitlines():
        if raw.strip().startswith("#") or not raw.strip():
            continue
        s = _strip_comment(raw).rstrip()
        if not s.strip():
            continue
        lines.append([len(s) - len(s.lstrip(" ")), s.strip()])
    if not lines:
        return {}
    value, _ = _block(lines, 0, lines[0][0])
    return value


def _strip_comment(s):
    quote = None
    for i, ch in enumerate(s):
        if ch in "\"'" and quote is None:
            quote = ch
        elif ch == quote:
            quote = None
        elif ch == "#" and quote is None and i > 0 and s[i - 1] == " ":
            return s[:i]
    return s


def _block(lines, i, indent):
    if lines[i][1].startswith("- ") or lines[i][1] == "-":
        out = []
        while i < len(lines) and lines[i][0] == indent and lines[i][1].startswith("-"):
            item = lines[i][1][1:].strip()
            if _KV.match(item):
                lines[i] = [indent + 2, item]
                value, i = _map(lines, i, indent + 2)
                out.append(value)
            else:
                out.append(_scalar(item))
                i += 1
        return out, i
    return _map(lines, i, indent)


def _map(lines, i, indent):
    out = {}
    while i < len(lines) and lines[i][0] == indent and not lines[i][1].startswith("- "):
        key, _, val = lines[i][1].partition(":")
        key, val = key.strip(), val.strip()
        i += 1
        if val:
            out[key] = _scalar(val)
        elif i < len(lines) and (lines[i][0] > indent or
                                 (lines[i][0] == indent and lines[i][1].startswith("- "))):
            out[key], i = _block(lines, i, lines[i][0])
        else:
            out[key] = None
    return out, i


def _scalar(v):
    if v == "{}":
        return {}
    if v.startswith("[") and v.endswith("]"):
        inner = v[1:-1].strip()
        return [_scalar(x.strip()) for x in _split_commas(inner)] if inner else []
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        return v[1:-1]
    low = v.lower()
    if low in ("true", "yes"):
        return True
    if low in ("false", "no"):
        return False
    if low in ("null", "~"):
        return None
    for cast in (int, float):
        try:
            return cast(v)
        except ValueError:
            pass
    return v


def _split_commas(s):
    parts, cur, quote = [], "", None
    for ch in s:
        if ch in "\"'" and quote is None:
            quote = ch
        elif ch == quote:
            quote = None
        if ch == "," and quote is None:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    parts.append(cur)
    return parts


def dump_flat(d):
    """Write a frontmatter mapping (one level deep, plus one nested map level)."""
    out = []
    for k, v in d.items():
        if isinstance(v, dict):
            out.append(f"{k}:")
            for k2, v2 in v.items():
                out.append(f"  {k2}: {_fmt(v2)}")
        else:
            out.append(f"{k}: {_fmt(v)}")
    return "\n".join(out) + "\n"


def _fmt(v):
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, list):
        return "[" + ", ".join(_fmt(x) for x in v) + "]"
    s = str(v)
    if s == "" or re.search(r"[:#\[\]{},]|^\s|\s$", s) or s.lower() in ("true", "false", "null", "yes", "no"):
        return '"' + s.replace('"', '\\"') + '"'
    return s
