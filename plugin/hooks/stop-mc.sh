#!/usr/bin/env bash
set -uo pipefail
if [ "${1:-}" = --selftest ]; then
p=0;f=0;t(){ "$@"&&p=$((p+1))||f=$((f+1)); }
t bash -n "$0"
kj=.claude/cairn/known-projects.json
run(){ CLAUDE_PLUGIN_ROOT="$1" HOME="$2" "$0" <<<'{"session_id":"a","transcript_path":"tp","cwd":"'"$3"'"}' &>/dev/null; }
w=$(mktemp -d);echo x >"$w/CLAUDE.md"
o=$("$0" <<<'{"session_id":"a","transcript_path":"b","cwd":"'"$w"'"}' 2>&1)
t [ -z "$o" -a ! -d "$w/.cairn" ]
echo '<!-- cairn:start -->' >"$w/CLAUDE.md";s=$w/pl/mission-control;mkdir -p "$s"
printf 'def parse_session(*a):\n (a[0]/"z").touch()\n' >"$s/parser.py"
h=$(mktemp -d)
run "$w/pl" "$h" "$w"
t [ -f "$w/.cairn/z" -a ! -f "$h/$kj" ]
pl=$(mktemp -d);h=$(mktemp -d)
ln -s "$(cd "${0%/*}/../mission-control"&&pwd)" "$pl/mission-control"
run "$pl" "$h" "$w"
run "$pl" "$h" "$w"
t [ "$(grep -c "$w" "$h/$kj")" = 1 -a -f "$h/.claude/cairn/pricing-check-state.json" ]
rm -rf $w $pl $h
echo "selftest: $p passed, $f failed"
exit $((f>0))
fi
command -v jq &>/dev/null || exit 0
IFS=$'\t' read -r si tp cwd <<<"$(jq -r '[.session_id,.transcript_path,.cwd]|map(.//"")|@tsv' 2>&-)"
[[ -n $si && -n $tp && -n $cwd ]] || exit 0
grep -qsF '<!-- cairn:start -->' "$cwd/CLAUDE.md" || exit 0
cd=$cwd/.cairn;mkdir -p "$cd" 2>&- || exit 0
[ -f "$cd/.gitignore" ] || echo '*' >"$cd/.gitignore" 2>&-
pr=${CLAUDE_PLUGIN_ROOT:-};[ "$pr" ] || exit 0
kp=
[[ $pr/ == "$cwd"/* ]] || { [ "${HOME:-}" ] && kp=$HOME/.claude/cairn/known-projects.json; }
python3 -c 'import json,sys
from pathlib import Path
tm,cd,tp,i,cw,kp=sys.argv[1:7]
try:sys.path.insert(0,tm);import parser;parser.parse_session(Path(cd),Path(tp),i)
except Exception:pass
try:
 if kp:
  k=Path(kp);k.parent.mkdir(parents=True,exist_ok=True);d=json.loads(k.read_text()) if k.exists() else []
  if cw not in d:import server;d.append(cw);server.write_known_projects(k,[Path(x)for x in d])
  import pricing_check as q;q.maybe_run(k,Path(cw),k.parent/"pricing-check-state.json")
except Exception:pass
' "$pr/mission-control" "$cd" "$tp" "$si" "$cwd" "$kp" >/dev/null
exit 0
