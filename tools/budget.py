#!/usr/bin/env python3
"""Budget gate for the cairn plugin repo. Checks the size and structure rules
in .harness/standards.md. stdlib only.

Usage:
    python tools/budget.py            human-readable findings, exit 0/1/2
    python tools/budget.py --json     findings as JSON
    python tools/budget.py --report   regenerate docs/BUDGET.md
"""
import argparse
import fnmatch
import json
import re
import subprocess
import sys
from pathlib import Path

RUNTIME_DIRS = ("agents", "skills", "commands", "hooks")
PLUGIN_DIR = "plugin"
FORBIDDEN_WRITE_PATHS = (
    ".claude/settings.json",
    ".claude/settings.local.json",
    ".claude/agents",
    ".claude/skills",
    ".claude/commands",
    ".claude/hooks",
)
HARNESS_FILE_CAPS = {
    "architecture.md": 40,
    "standards.md": 40,
    "environment.md": 30,
    "workflow.md": 30,
}
MANDATE_RE = re.compile(r"\b(MUST|ALWAYS|NEVER|MANDATORY|NON-NEGOTIABLE)\b")
HARD_REQ_RE = re.compile(r"(?m)^#{1,6}\s*HARD REQUIREMENTS\s*$")
PLACEHOLDER_TOKENS = ("TODO", "TBD", "FIXME", "<placeholder")
AT_IMPORT_RE = re.compile(r"(?<!\S)@([\w./~-]+)")


def repo_root() -> Path:
    p = Path(__file__).resolve().parent
    while p != p.parent:
        if (p / ".git").exists():
            return p
        p = p.parent
    return Path(__file__).resolve().parent.parent


def plugin_root(root):
    """The plugin's own root: `plugin/` when it holds the manifest, else the repo root."""
    p = root / PLUGIN_DIR
    return p if (p / ".claude-plugin" / "plugin.json").exists() else root


class Finding:
    def __init__(self, rule, path, severity, detail):
        self.rule = rule
        self.path = path
        self.severity = severity  # "warning" | "error"
        self.detail = detail

    def line(self):
        return f"[{self.severity.upper()}] {self.rule}: {self.path} — {self.detail}"

    def to_dict(self):
        return {"rule": self.rule, "path": self.path, "severity": self.severity, "detail": self.detail}


def parse_frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.DOTALL)
    if not m:
        return {}, text
    fm_text, body = m.group(1), m.group(2)
    fields = {}
    for line in fm_text.splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            fields[key.strip()] = val.strip()
    return fields, body


def read_text(path):
    return path.read_text(encoding="utf-8", errors="replace")


def frontmatter_bytes(text):
    """Bytes in the leading frontmatter block; the whole text if it has none or is unclosed."""
    _, body = parse_frontmatter(text)
    if body == text:
        return len(text.encode())
    return len(text.encode()) - len(body.encode())


def cap_check(rule, label, measured, unit, soft, hard):
    findings = []
    if hard is not None and measured > hard:
        findings.append(Finding(rule, label, "error", f"{measured} {unit} exceeds hard cap {hard} {unit}"))
    elif soft is not None and measured > soft:
        findings.append(Finding(rule, label, "warning", f"{measured} {unit} exceeds soft cap {soft} {unit}"))
    return findings


def headroom(measured, hard, unit="B"):
    if hard is None:
        return "-"
    return f"{hard - measured} {unit}"


IGNORED_DIR_PARTS = (".git", "__pycache__", ".pytest_cache", "node_modules")


def all_files(root):
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        if any(part in IGNORED_DIR_PARTS for part in p.relative_to(root).parts):
            continue
        rel = p.relative_to(root).as_posix()
        yield p, rel


def scan(root):
    """Walk the repo once. Returns (findings, report_rows, always_loaded_total)."""
    findings = []
    rows = []  # (path, measured, unit, load_class, headroom)
    always_loaded_total = 0
    agents = []  # (path, fields, tools set)
    pre = plugin_root(root).relative_to(root).as_posix() + "/"
    pre = "" if pre == "./" else pre

    for path, rel in all_files(root):
        # prel: path relative to the plugin root, or "" for files outside it
        prel = rel[len(pre):] if rel.startswith(pre) else ""
        if prel.startswith("agents/") and prel.endswith(".md") and prel.count("/") == 1:
            text = read_text(path)
            fields, body = parse_frontmatter(text)
            desc = fields.get("description", "")
            desc_bytes = len(desc.encode())
            body_bytes = len(body.encode())
            findings += cap_check("agent-description", rel, desc_bytes, "B", 250, 300)
            findings += cap_check("agent-body", rel, body_bytes, "B", 3000, 4096)
            rows.append((f"{rel} (description)", desc_bytes, "B", "always-loaded", headroom(desc_bytes, 300)))
            rows.append((f"{rel} (body)", body_bytes, "B", "on-demand", headroom(body_bytes, 4096)))
            always_loaded_total += desc_bytes
            tools = {t.strip() for t in fields.get("tools", "").split(",") if t.strip()}
            agents.append((rel, fields, tools))
            continue

        if fnmatch.fnmatch(prel, "skills/*/SKILL.md"):
            text = read_text(path)
            fields, _ = parse_frontmatter(text)
            size = len(text.encode())
            findings += cap_check("skill-md", rel, size, "B", 3000, 4096)
            rows.append((rel, size, "B", "on-demand", headroom(size, 4096)))
            desc_bytes = len(fields.get("description", "").encode())
            always_loaded_total += desc_bytes
            continue

        if fnmatch.fnmatch(prel, "skills/*/reference/*.md"):
            size = len(read_text(path).encode())
            findings += cap_check("skill-reference", rel, size, "B", 6000, 8192)
            rows.append((rel, size, "B", "on-demand", headroom(size, 8192)))
            continue

        if fnmatch.fnmatch(prel, "commands/*.md"):
            text = read_text(path)
            fields, _ = parse_frontmatter(text)
            size = len(text.encode())
            findings += cap_check("command-file", rel, size, "B", 1500, 2048)
            rows.append((rel, size, "B", "on-demand", headroom(size, 2048)))
            always_loaded_total += len(fields.get("description", "").encode())
            continue

        if fnmatch.fnmatch(prel, "hooks/*"):
            size = len(read_text(path).encode()) if is_text_file(path) else path.stat().st_size
            findings += cap_check("hook-script", rel, size, "B", 1500, 2048)
            rows.append((rel, size, "B", "executed", headroom(size, 2048)))
            continue

        if fnmatch.fnmatch(rel, ".harness/*.md") and not rel.startswith(".harness/local/"):
            n = len(read_text(path).splitlines())
            hard = HARNESS_FILE_CAPS.get(Path(rel).name, 60)
            findings += cap_check("harness-file", rel, n, "lines", hard, hard)
            rows.append((rel, n, "lines", "on-demand (consuming project)", headroom(n, hard, "lines")))
            continue

        if rel == ".harness/local/preferences.md":
            n = len(read_text(path).splitlines())
            findings += cap_check("harness-local-prefs", rel, n, "lines", 20, 30)
            rows.append((rel, n, "lines", "on-demand (consuming project)", headroom(n, 30, "lines")))
            continue

        if fnmatch.fnmatch(rel.lower(), "docs/tasks/*/plan*.md"):
            size = len(read_text(path).encode())
            findings += cap_check("task-plan", rel, size, "B", 8000, 12288)
            continue

        if fnmatch.fnmatch(rel, "docs/tasks/*/STATE.md"):
            size = frontmatter_bytes(read_text(path))
            findings += cap_check("task-state", rel, size, "B", 800, 1024)
            continue

        if prel == "skills/task-assets/assets/claude-md-marker.md":
            size = len(read_text(path).encode())
            findings += cap_check("claude-md-marker", rel, size, "B", 250, 400)
            rows.append((rel, size, "B", "on-demand", headroom(size, 400)))
            continue

        if rel == "CLAUDE.md":
            size = len(read_text(path).encode())
            findings += cap_check("plugin-claude-md", rel, size, "B", 3000, 4096)
            rows.append((rel, size, "B", "always-loaded (this repo)", headroom(size, 4096)))
            continue

        if prel.endswith(".md") and (prel.startswith("skills/") or prel.startswith("commands/")):
            size = len(read_text(path).encode())
            findings += cap_check("runtime-md-catchall", rel, size, "B", None, 8192)
            rows.append((rel, size, "B", "on-demand", headroom(size, 8192)))
            continue

        if rel in ("docs/REGISTRY.md", "docs/BUDGET.md") or rel.startswith("tools/") or rel.startswith(".github/"):
            size = path.stat().st_size
            load_class = "executed" if rel.startswith("tools/") or rel.startswith(".github/") else "never-loaded"
            rows.append((rel, size, "B", load_class, "-"))
            continue

    findings += cap_check(
        "always-loaded-frontmatter-total", "(all agents + skills + commands descriptions)",
        always_loaded_total, "B", 2500, 3000,
    )
    return findings, rows, always_loaded_total, agents


def is_text_file(path):
    try:
        path.read_text(encoding="utf-8")
        return True
    except (UnicodeDecodeError, OSError):
        return False


def check_at_imports(root):
    findings = []
    for path in sorted(root.rglob("*.md")):
        if any(part in IGNORED_DIR_PARTS for part in path.relative_to(root).parts):
            continue
        rel = path.relative_to(root).as_posix()
        for m in AT_IMPORT_RE.finditer(read_text(path)):
            findings.append(Finding("no-at-imports", rel, "error", f"@-import found: @{m.group(1)}"))
    return findings


def check_reference_tables(root):
    findings = []
    skills_dir = plugin_root(root) / "skills"
    if not skills_dir.exists():
        return findings
    for skill_dir in sorted(p for p in skills_dir.iterdir() if p.is_dir()):
        ref_dir = skill_dir / "reference"
        if not ref_dir.exists():
            continue
        skill_md = skill_dir / "SKILL.md"
        skill_text = read_text(skill_md) if skill_md.exists() else ""
        for ref_file in sorted(ref_dir.glob("*.md")):
            rel = ref_file.relative_to(root).as_posix()
            if f"reference/{ref_file.name}" not in skill_text:
                findings.append(Finding("reference-table-orphan", rel, "error",
                                         f"not named in {skill_dir.name}/SKILL.md's Load-when table"))
    return findings


def check_placeholders(root):
    findings = []
    for d in RUNTIME_DIRS:
        base = plugin_root(root) / d
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file() or not is_text_file(path):
                continue
            rel = path.relative_to(root).as_posix()
            text = read_text(path)
            for token in PLACEHOLDER_TOKENS:
                if token in text:
                    findings.append(Finding("no-placeholders", rel, "error", f"contains '{token}'"))
    return findings


def check_mandate_language(root):
    findings = []
    for d in RUNTIME_DIRS:
        base = plugin_root(root) / d
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file() or not is_text_file(path):
                continue
            rel = path.relative_to(root).as_posix()
            text = read_text(path)
            hits = sorted(set(MANDATE_RE.findall(text)))
            for hit in hits:
                findings.append(Finding("no-mandate-language", rel, "error", f"contains mandate word '{hit}'"))
            if HARD_REQ_RE.search(text):
                findings.append(Finding("no-mandate-language", rel, "error", "contains a 'HARD REQUIREMENTS' heading"))
    return findings


def check_registry(root, agents):
    findings = []
    registry_path = root / "docs" / "REGISTRY.md"
    if not agents:
        return findings
    if not registry_path.exists():
        return [Finding("agent-tool-registry", "docs/REGISTRY.md", "error",
                         "missing while agent files exist under the plugin's agents/")]
    text = read_text(registry_path)
    sections = {}
    current = None
    for line in text.splitlines():
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m:
            current = m.group(1).strip()
            sections[current] = set()
            continue
        m = re.match(r"^-\s+(\S+)", line)
        if m and current is not None:
            sections[current].add(m.group(1))

    review_re = re.compile(r"review|audit|check", re.IGNORECASE)
    for rel, fields, tools in agents:
        name = fields.get("name", "")
        justified = sections.get(name, set())
        for tool in sorted(tools - justified):
            findings.append(Finding("agent-tool-registry", rel, "error",
                                     f"tool '{tool}' not justified for '{name}' in docs/REGISTRY.md"))
        haystack = f"{name} {fields.get('description', '')}"
        if review_re.search(haystack) and ("Write" in tools or "Edit" in tools):
            findings.append(Finding("reviewer-read-only", rel, "error",
                                     f"'{name}' matches review/audit/check but grants Write/Edit"))
    return findings


def check_shell_selftest(root):
    findings = []
    tools_dir = root / "tools"
    if not tools_dir.exists():
        return findings
    for path in sorted(tools_dir.rglob("*.sh")):
        rel = path.relative_to(root).as_posix()
        text = read_text(path)
        if "--selftest" not in text:
            findings.append(Finding("shell-selftest", rel, "error", "no --selftest handler found"))
            continue
        result = subprocess.run([str(path), "--selftest"], capture_output=True)
        if result.returncode != 0:
            findings.append(Finding("shell-selftest", rel, "error",
                                     f"--selftest exited {result.returncode}"))
    return findings


def check_forbidden_paths(root):
    findings = []
    for d in RUNTIME_DIRS:
        base = plugin_root(root) / d
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file() or not is_text_file(path):
                continue
            rel = path.relative_to(root).as_posix()
            text = read_text(path)
            for forbidden in FORBIDDEN_WRITE_PATHS:
                if forbidden in text:
                    findings.append(Finding("no-forbidden-write-paths", rel, "error",
                                             f"names forbidden consuming-project path '{forbidden}'"))
    return findings


def gather_findings(root):
    findings, rows, always_loaded_total, agents = scan(root)
    findings += check_at_imports(root)
    findings += check_reference_tables(root)
    findings += check_placeholders(root)
    findings += check_mandate_language(root)
    findings += check_registry(root, agents)
    findings += check_shell_selftest(root)
    findings += check_forbidden_paths(root)
    return findings, rows, always_loaded_total


def write_report(root, rows, always_loaded_total):
    docs_dir = root / "docs"
    docs_dir.mkdir(exist_ok=True)
    consuming = [r for r in rows if r[3] == "on-demand (consuming project)"]
    own = [r for r in rows if r not in consuming]

    def table(rs):
        out = ["| Path | Measured | Load class | Cap headroom |", "|---|---|---|---|"]
        for path, measured, unit, load_class, hr in rs:
            out.append(f"| {path} | {measured} {unit} | {load_class} | {hr} |")
        return out

    lines = [
        "# Budget ledger",
        "",
        "Generated by `tools/budget.py --report`. Do not hand-edit.",
        "",
        "## This repo",
        "",
        *table(own),
        "",
        f"**Always-loaded frontmatter total: {always_loaded_total} B / 3000 B ceiling**",
        "",
    ]
    if consuming:
        lines += ["## Templates for a consuming project", "", *table(consuming), ""]
    (docs_dir / "BUDGET.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--report", action="store_true")
    args = parser.parse_args()

    try:
        root = repo_root()
        findings, rows, always_loaded_total = gather_findings(root)
        if args.report:
            write_report(root, rows, always_loaded_total)
    except Exception as exc:  # internal error
        print(f"budget.py: internal error: {exc}", file=sys.stderr)
        sys.exit(2)

    if args.json:
        print(json.dumps([f.to_dict() for f in findings], indent=2))
    else:
        if not findings:
            print("budget.py: clean")
        for f in findings:
            print(f.line())

    errors = [f for f in findings if f.severity == "error"]
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
