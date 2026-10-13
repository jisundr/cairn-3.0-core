#!/usr/bin/env bash
set -uo pipefail
if [ "${1:-}" = --selftest ]; then
f=0;t(){ "$@"||f=$((f+1)); }
h=$(mktemp -d);d="$h/.claude/cairn/active";mkdir -p "$d" "$h/p/.cairn"
echo '{"project":"/p","task":"x"}' >"$d/s1.json"
r(){ HOME="$h" "$0" "$1" <<<"{\"session_id\":\"$2\",\"agent_id\":\"a1\"}" 2>&1; }
o=$(r start s1)
t jq -e '.task=="x" and .schema==1 and (.started|endswith("Z"))' "$d/s1--a1.active" >/dev/null
t jq -e '.hookSpecificOutput|.hookEventName=="SubagentStart" and (.additionalContext|contains("s1--a1.active"))' <<<"$o" >/dev/null
t [ -z "$(r start no)" -a ! -e "$d/no--a1.active" ]
r stop s1
t [ ! -e "$d/s1--a1.active" ]
echo '{"project":"'$h'/p","task":"t1","started":"2020-01-01T00:00:00Z"}' >"$d/s2--a1.active"
r stop s2
t jq -e '.session=="s2" and .start<.end' "$h/p/.cairn/task-sessions.jsonl" >/dev/null
touch "$d/new--b.active";touch -t 202001010000 "$d/old--a.active"
r sweep s1
t [ ! -e "$d/old--a.active" -a -e "$d/new--b.active" ]
rm -rf "$h"
echo "subagent-marker.sh selftest: $f failed"
exit $((f>0))
fi
d="${HOME:-/x}/.claude/cairn/active"
{ read -r s;read -r a; } < <(jq -r '.session_id//"",.agent_id//""' 2>/dev/null)
case "${1:-}" in
start)
[ "$s" -a "$a" -a -f "$d/$s.json" ] || exit 0
b="$(jq -c --arg t "$(date -u +%FT%TZ)" '{project,task}|select(all(.[];type=="string"))|.+{schema:1,started:$t}' "$d/$s.json")"
m="$([ "$b" ] && mktemp "$d/.marker.XXXXXX")" || exit 0
echo "$b" >"$m" && mv "$m" "$d/$s--$a.active" && printf '{"hookSpecificOutput":{"hookEventName":"SubagentStart","additionalContext":"Marker: %s--%s.active. With a sub-task folder, follow cairn:shared reference/marker-task.md first."}}\n' "$s" "$a" || rm -f "$m";;
stop) [ "$s" -a "$a" ] || exit 0
f="$d/$s--$a.active";p="$(jq -r '.project//""' "$f" 2>&-)"
[ "${p:0:1}" = / -a -d "$p/.cairn" ] && jq -c --arg s "$s" --arg e "$(date -u +%FT%TZ)" '{session:$s,project,task,start:(.started//$e),end:$e}' "$f" >>"$p/.cairn/task-sessions.jsonl" 2>&-
rm -f "$f";;
sweep) find "$d" -name '*.active' -mmin +240 -delete 2>/dev/null;;
esac
exit 0
