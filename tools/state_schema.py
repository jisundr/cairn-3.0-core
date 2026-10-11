#!/usr/bin/env python3
"""Validate a task folder's STATE.md frontmatter against schema 1.

The schema is published in docs/schemas/state-v1.md; this is its executable
form. stdlib only, with its own small parser so it does not depend on
mission-control (which leaves core). tools/test_state_schema.py pins the
parser to mission-control/tasks.py and the caps to tools/budget.py.

    python tools/state_schema.py PATH...

PATH is a STATE.md file or a directory searched for STATE.md files; folders
named _template are skipped unless named directly. Exit 0 when no errors,
1 otherwise, 2 when there is nothing to check.
"""
import re
import sys
from pathlib import Path

SCHEMA_VERSION = 1
FIELD_CAP = 200  # characters per field
BLOCK_SOFT = 800  # bytes, frontmatter block
BLOCK_HARD = 1024

REQUIRED = ("goal", "key_info")
LIST_FIELDS = ("paths", "out_of_scope", "depends_on", "flags")
SCALAR_FIELDS = ("schema", "goal", "done_when", "source", "path", "key_info")
# 2.0 files wrote these two as a plain scalar; schema 1 still reads them.
DEPRECATED_SCALAR_LISTS = ("depends_on", "flags")
KNOWN = set(LIST_FIELDS) | set(SCALAR_FIELDS)

_KEY_LINE_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*):(.*)$")


class Finding:
    def __init__(self, severity, field, message, name=""):
        self.severity = severity  # "error" | "warning"
        self.field = field
        self.message = message
        self.name = name

    def line(self):
        where = f"{self.name}: " if self.name else ""
        what = f"{self.field}: " if self.field else ""
        return f"[{self.severity.upper()}] {where}{what}{self.message}"

    def __repr__(self):
        return f"Finding({self.severity!r}, {self.field!r}, {self.message!r})"


def _bounds(lines):
    """(start, end) of the lines between the delimiters, or None when the
    file does not open with `---` or never closes it."""
    if not lines or lines[0].strip() != "---":
        return None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return (1, i)
    return None


def _strip_quotes(value):
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def _split_flow(inner):
    """Split a flow list's inner text on top-level commas; commas inside
    quoted items stay."""
    items, current, quote = [], [], ""
    for ch in inner:
        if quote:
            current.append(ch)
            if ch == quote:
                quote = ""
        elif ch in "\"'":
            quote = ch
            current.append(ch)
        elif ch == ",":
            items.append("".join(current))
            current = []
        else:
            current.append(ch)
    items.append("".join(current))
    return items


def parse(text):
    """Frontmatter as a dict of str or list[str]; {} when there is none."""
    lines = text.splitlines()
    bounds = _bounds(lines)
    if bounds is None:
        return {}
    result = {}
    key, items = None, None
    for line in lines[bounds[0]:bounds[1]]:
        if items is not None:
            stripped = line.strip()
            if stripped.startswith("- "):
                items.append(_strip_quotes(stripped[2:]))
                continue
            result[key] = items
            key, items = None, None
        m = _KEY_LINE_RE.match(line)
        if not m:
            continue
        k, raw = m.group(1), m.group(2).strip()
        if raw == "":
            key, items = k, []
        elif raw.startswith("[") and raw.endswith("]"):
            inner = raw[1:-1].strip()
            result[k] = [] if inner == "" else [_strip_quotes(i) for i in _split_flow(inner)]
        else:
            result[k] = _strip_quotes(raw)
    if items is not None:
        result[key] = items
    return result


def _block_bytes(text):
    """Bytes of the frontmatter block including both delimiters, measured the
    way tools/budget.py measures it for LF files; None if the block is
    unclosed. Uses _bounds, so any file validate() reads as having a block is
    measured too (CRLF and padded delimiters included)."""
    lines = text.splitlines(keepends=True)
    bounds = _bounds(lines)
    if bounds is None:
        return None
    return sum(len(line.encode()) for line in lines[: bounds[1] + 1])


# Scalar forms 2.0 files used for list fields. Accepted with a warning.
_NONE_SCALARS = {"none", "\u2014", "\u2013", "-", "n/a"}


def _scalar_list_warning(field, value):
    """Warning text for a list field written as a scalar, naming the rewrite."""
    v = value.strip()
    if v.lower() in _NONE_SCALARS:
        return f"scalar {v!r} for no entries is deprecated; write `{field}: []` or drop the key"
    if field == "depends_on":
        items = [i.strip() for i in v.split(",") if i.strip()]
        return f"scalar is deprecated; write `{field}: [{', '.join(items)}]`"
    return f"scalar is deprecated; wrap the text as a one-item list, `{field}: [<text>]`"


def _empty(value):
    return value == "" or value == []


def validate(text, name=""):
    """Findings for one STATE.md's text. An empty list means clean."""
    out = []

    def add(sev, field, msg):
        out.append(Finding(sev, field, msg, name))

    if _bounds(text.splitlines()) is None:
        add("error", None, "no frontmatter: file must open with --- and close the block with ---")
        return out
    fm = parse(text)

    for field in REQUIRED:
        if field not in fm:
            add("error", field, "required field is missing")
        elif _empty(fm[field]):
            add("warning", field, "required field is empty")

    if "schema" in fm:
        raw = fm["schema"]
        if not isinstance(raw, str) or not re.fullmatch(r"[0-9]+", raw) or int(raw) < 1:
            add("error", "schema", f"must be a positive integer, got {raw!r}")
        elif int(raw) > SCHEMA_VERSION:
            add("warning", "schema", f"newer than this validator knows ({SCHEMA_VERSION}); read best-effort")

    for field in LIST_FIELDS:
        if field in fm and isinstance(fm[field], str):
            if field in DEPRECATED_SCALAR_LISTS:
                if fm[field].strip():
                    add("warning", field, _scalar_list_warning(field, fm[field]))
            else:
                add("error", field, "must be a list ([a, b] or - items), got a scalar")
    for field in ("goal", "key_info", "done_when", "source", "path"):
        if field in fm and isinstance(fm[field], list) and fm[field]:
            add("error", field, "must be a scalar, got a list")

    for field, value in fm.items():
        if field not in KNOWN:
            add("warning", field, "unknown key (readers ignore it)")
        rendered = value if isinstance(value, str) else ", ".join(value)
        if len(rendered) >= FIELD_CAP:
            add("warning", field, f"{len(rendered)} chars, keep under {FIELD_CAP}")

    size = _block_bytes(text)
    if size is not None:
        if size > BLOCK_HARD:
            add("error", None, f"frontmatter is {size} B, over the {BLOCK_HARD} B cap")
        elif size > BLOCK_SOFT:
            add("warning", None, f"frontmatter is {size} B, over the {BLOCK_SOFT} B soft cap")
    return out


def collect(paths):
    """STATE.md files named by paths: files as given, directories searched,
    skipping _template folders found by the search."""
    files = []
    for p in paths:
        p = Path(p)
        if p.is_dir():
            named = p / "STATE.md"
            if named.is_file():
                files.append(named)
            for f in sorted(p.rglob("STATE.md")):
                if f != named and "_template" not in f.relative_to(p).parts:
                    files.append(f)
        else:
            files.append(p)
    return files


def main(argv):
    if not argv:
        print("usage: state_schema.py PATH...", file=sys.stderr)
        return 2
    files = collect(argv)
    if not files:
        print("no STATE.md files found", file=sys.stderr)
        return 2
    errors = 0
    for f in files:
        try:
            text = f.read_text(encoding="utf-8")
        except OSError as e:
            print(f"[ERROR] {f}: {e}")
            errors += 1
            continue
        findings = validate(text, str(f))
        for item in findings:
            print(item.line())
        errors += sum(1 for item in findings if item.severity == "error")
        if not findings:
            print(f"ok {f}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
