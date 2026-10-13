#!/usr/bin/env bash
set -uo pipefail
if [ "${1:-}" = --selftest ]; then
p=0;f=0;t(){ "$@"&&p=$((p+1))||f=$((f+1)); }
t bash -n "$0"
w=$(mktemp -d);h=$(mktemp -d);export CLAUDE_PLUGIN_ROOT=${0%/*}/.. HOME=$h
j='{"session_id":"s","cwd":"'$w'"}'
t "$0" <<<'not json'
"$0" <<<"$j"
t [ ! -e "$w/.cairn" ]
echo '<!-- cairn:start -->' >"$w/CLAUDE.md"
mkdir -p "$w/docs/tasks/2026-01-01-0900-build-x"
printf -- '---\ngoal: g\nkey_info: done\n---\n' >"$w/docs/tasks/2026-01-01-0900-build-x/STATE.md"
"$0" <<<"$j"
t [ "$(jq -r '.schema,.tasks[0].phase' "$w/.cairn/export/tasks.json" | tr '\n' ' ')" = "1 done " ]
t [ "$(cat "$w/.cairn/.gitignore")" = '*' ]
rm -rf "$w" "$h"
echo "export-tasks.sh selftest: $p passed, $f failed"
exit $((f>0))
fi
command -v jq python3 &>/dev/null || exit 0
IFS=$'\t' read -r si cwd <<<"$(jq -r '[.session_id,.cwd]|map(.//"")|@tsv' 2>&-)"
[[ -n $si && -n $cwd ]] || exit 0
grep -qsF '<!-- cairn:start -->' "$cwd/CLAUDE.md" || exit 0
c=$cwd/.cairn;mkdir -p "$c" 2>&- || exit 0
[ -f "$c/.gitignore" ] || echo '*' >"$c/.gitignore" 2>&-
python3 "${CLAUDE_PLUGIN_ROOT:-}/skills/task-assets/assets/tasks-export.py" --root "$cwd" --session "$si" &>/dev/null
exit 0
