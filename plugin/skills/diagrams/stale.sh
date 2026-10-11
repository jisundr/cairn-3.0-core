#!/usr/bin/env bash
# Lists every rendered diagram SVG older than its source (<name>.mmd or
# <name>.gen.mjs beside <name>.svg). Run from the project root:
#   stale.sh [dir ...]     (default: docs)
# Exit 0 when every SVG is current, 1 when any is stale or missing.
# Committed files compare by last commit time (a fresh clone resets mtimes);
# an uncommitted edit counts as newer than a committed file; two uncommitted
# files, or no git, compare by mtime.
set -uo pipefail

in_git() { git rev-parse --is-inside-work-tree >/dev/null 2>&1; }
dirty() { [ -n "$(git status --porcelain -- "$1" 2>/dev/null)" ]; }
ctime() { git log -1 --format=%ct -- "$1" 2>/dev/null; }

# Prints a reason and returns 0 when $2 (svg) is stale against $1 (source).
stale_pair() {
  local src=$1 svg=$2
  if [ ! -f "$svg" ]; then echo "never rendered"; return 0; fi
  if in_git; then
    local sd=0 vd=0
    dirty "$src" && sd=1
    dirty "$svg" && vd=1
    if [ $sd = 1 ] && [ $vd = 0 ]; then echo "source edited since last render"; return 0; fi
    if [ $sd = 0 ] && [ $vd = 1 ]; then return 1; fi
    if [ $sd = 0 ] && [ $vd = 0 ]; then
      local st vt
      st=$(ctime "$src"); vt=$(ctime "$svg")
      if [ -n "$st" ] && [ -n "$vt" ] && [ "$st" -gt "$vt" ]; then
        echo "source committed after the SVG"; return 0
      fi
      return 1
    fi
  fi
  if [ "$src" -nt "$svg" ]; then echo "source newer than the SVG"; return 0; fi
  return 1
}

run() {
  local found=0 dir src svg why
  [ $# -eq 0 ] && set -- docs
  for dir in "$@"; do
    [ -d "$dir" ] || continue
    while IFS= read -r src; do
      case $src in
        *.gen.mjs) svg=${src%.gen.mjs}.svg ;;
        *) svg=${src%.mmd}.svg ;;
      esac
      if why=$(stale_pair "$src" "$svg"); then
        echo "stale: $svg ($why; source $src)"; found=1
      fi
    done < <(find "$dir" -type f \( -name '*.mmd' -o -name '*.gen.mjs' \) -not -path '*/node_modules/*' | sort)
  done
  [ $found = 0 ] && echo "diagrams: all current"
  return $found
}

selftest() {
  local t; t=$(mktemp -d) || return 1
  trap 'rm -rf "$t"' RETURN
  (
    cd "$t" || exit 1
    set +o pipefail  # run exits 1 on stale; the grep decides
    mkdir -p docs/d
    printf 'flowchart LR\n' > docs/d/a.mmd; printf '<svg/>' > docs/d/a.svg
    printf '' > docs/d/b.gen.mjs
    touch -d '2020-01-01' docs/d/a.mmd; touch -d '2021-01-01' docs/d/a.svg
    out=$(run docs) && exit 1
    echo "$out" | grep -q 'docs/d/b.svg (never rendered' || exit 1
    echo "$out" | grep -q 'a.svg' && exit 1
    printf '<svg/>' > docs/d/b.svg; touch -d '2019-01-01' docs/d/b.svg
    run docs | grep -q 'docs/d/b.svg (source newer' || exit 1
    touch docs/d/b.svg
    run docs >/dev/null || exit 1
    command -v git >/dev/null || exit 0
    ci() { GIT_COMMITTER_DATE="$1" git -c user.name=t -c user.email=t@t commit -qm "$1"; }
    git init -q . && git add -A && ci 2020-01-01T00:00:00 || exit 1
    touch -d '2000-01-01' docs/d/a.svg
    run docs >/dev/null || exit 1
    printf 'flowchart TD\n' > docs/d/a.mmd; touch -d '2000-01-01' docs/d/a.mmd
    run docs | grep -q 'a.svg (source edited' || exit 1
    git add -A && ci 2021-01-01T00:00:00 || exit 1
    run docs | grep -q 'a.svg (source committed after' || exit 1
    printf '<svg></svg>' > docs/d/a.svg
    run docs >/dev/null || exit 1
    git add -A && ci 2022-01-01T00:00:00 || exit 1
    run docs >/dev/null || exit 1
    exit 0
  )
}

if [ "${1:-}" = "--selftest" ]; then
  selftest && { echo "stale.sh: selftest ok"; exit 0; }
  echo "stale.sh: selftest failed" >&2; exit 1
fi
run "$@"
