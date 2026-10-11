#!/usr/bin/env bash
# PreToolUse on Read|Glob|Grep: allow without a prompt when the target is inside
# this plugin's own folder. Anything else gets no output, so normal permissions apply.
set -uo pipefail
if [ "${1:-}" = --selftest ]; then
f=0;t(){ "$@"||f=$((f+1)); }
r=$(mktemp -d);mkdir -p "$r/skills";touch "$r/skills/a.md"
run(){ CLAUDE_PLUGIN_ROOT="$r" "$0" <<<"$1" 2>/dev/null; }
ok(){ jq -e '.hookSpecificOutput.permissionDecision=="allow"' >/dev/null <<<"$1"; }
t ok "$(run '{"tool_name":"Read","tool_input":{"file_path":"'"$r"'/skills/a.md"}}')"
t ok "$(run '{"tool_name":"Glob","tool_input":{"pattern":"*.md","path":"'"$r"'/skills"}}')"
t ok "$(run '{"tool_name":"Grep","tool_input":{"pattern":"x","path":"'"$r"'"}}')"
t [ -z "$(run '{"tool_name":"Read","tool_input":{"file_path":"/etc/passwd"}}')" ]
t [ -z "$(run '{"tool_name":"Read","tool_input":{"file_path":"'"$r"'/../x"}}')" ]
t [ -z "$(run '{"tool_name":"Read","tool_input":{"file_path":"'"$r"'x/a.md"}}')" ]
t [ -z "$(run '{"tool_name":"Edit","tool_input":{"file_path":"'"$r"'/skills/a.md"}}')" ]
t [ -z "$(run '{"tool_name":"Glob","tool_input":{"pattern":"*.md"}}')" ]
t [ -z "$(CLAUDE_PLUGIN_ROOT= "$0" <<<'{"tool_name":"Read","tool_input":{"file_path":"/a"}}')" ]
rm -rf "$r"
echo "allow-plugin-read.sh selftest: $f failed"
exit $((f>0))
fi
root="${CLAUDE_PLUGIN_ROOT:-}"
[ -n "$root" ] && command -v jq >/dev/null 2>&1 || exit 0
real="$(cd "$root" 2>/dev/null && pwd -P)" || exit 0;root="${root%/}"
IFS=$'\t' read -r tool p <<<"$(jq -r '[.tool_name//"", (.tool_input.file_path // .tool_input.path // "")]|@tsv' 2>/dev/null)"
case "$tool" in Read|Glob|Grep) ;; *) exit 0;; esac
case "/$p/" in */../*) exit 0;; esac
under(){ [ "$p" = "$1" ] || [ "${p#"$1"/}" != "$p" ]; }
under "$root" || under "$real" || exit 0
printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow","permissionDecisionReason":"cairn reading its own plugin files"}}\n'
exit 0
