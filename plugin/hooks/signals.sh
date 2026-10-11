#!/usr/bin/env bash
set -uo pipefail
if [ "${1:-}" = --selftest ]; then
p=0;f=0;t(){ "$@"&&p=$((p+1))||f=$((f+1)); }
t bash -n "$0"
w=$(mktemp -d);export CLAUDE_PLUGIN_ROOT=${0%/*}/..
j='{"session_id":"s","transcript_path":"'$w'/t","cwd":"'$w'"}'
t "$0" record <<<'not json'
t "$0" count <<<"$j"
echo '<!-- cairn:start -->' >"$w/CLAUDE.md"
echo '{"type":"user","message":{"content":"No, use tabs here"}}' >"$w/t"
"$0" record <<<"$j"
t [ "$(grep -c '"status":"queued"' "$w"/.cairn/proposals/*.json)" = 1 ]
o=$("$0" count <<<"$j")
t [ "${o:0:8}" = "cairn: 1" -a -z "$("$0" count <<<"$j")" ]
rm -rf "$w"
echo "selftest: $p passed, $f failed"
exit $((f>0))
fi
command -v jq &>/dev/null || exit 0
IFS=$'\t' read -r si cwd tp <<<"$(jq -r '[.session_id,.cwd,.transcript_path]|map(.//"")|@tsv' 2>&-)"
[[ -n $si && -n $cwd ]] || exit 0
grep -qsF '<!-- cairn:start -->' "$cwd/CLAUDE.md" || exit 0
d=$cwd/.cairn/proposals;mkdir -p "$d" 2>&- || exit 0
[ -f "$d/../.gitignore" ] || echo '*' >"$d/../.gitignore" 2>&-
case ${1:-} in
record) [ -n "$tp" ] && python3 "${CLAUDE_PLUGIN_ROOT:-}/skills/task-assets/assets/proposals.py" record --root "$cwd" --session "$si" --transcript "$tp" &>/dev/null;;
count) n=$(find "$d" -name '*.json' -mtime -30 -exec grep -lF '"status":"queued"' {} + 2>&-|wc -l);n=$((n+0))
[ $n -gt 0 ] && [ "$(cat "$d/.announced" 2>&-)" != "$si" ] && { echo "$si" >"$d/.announced"
echo "cairn: $n rule proposals queued. Mention once; the user can run /cairn-retro to review.";};;
esac
exit 0
