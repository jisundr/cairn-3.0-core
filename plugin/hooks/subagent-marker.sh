#!/usr/bin/env bash
set -uo pipefail
if [ "${1:-}" = --selftest ]; then
bash -n "$0" || exit 1
h=$(mktemp -d);d="$h/.claude/cairn/active";mkdir -p "$d"
echo '{"project":"/p","task":"x"}' >"$d/s1.json"
i='{"session_id":"s1","agent_id":"a1"}'
HOME="$h" "$0" start <<<"$i" >/dev/null;[ -f "$d/s1--a1.active" ];f=$?
HOME="$h" "$0" stop <<<"$i";[ ! -e "$d/s1--a1.active" ] && exit $f
exit 1
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
