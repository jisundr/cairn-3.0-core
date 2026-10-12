# Rule format

A rule is one bullet on one line in `.harness/{architecture,standards,environment,workflow}.md`:

`- <rule text> | evidence: <type>:<value> | applies when: <trigger>`

Both annotations are optional. The delimiters are the literal ` | evidence: ` and ` | applies when: `, in that order; a `|` elsewhere in the text is fine. A rule with neither is a 2.0 rule: valid, loads always, reported as legacy.

Not rules, never annotated: the `>` header, headings, non-bullets, bullets under `## Gates`, `## Release` or `## Archive`, typed preconditions, fenced blocks, anything under `.harness/local/`.

## Evidence (one item)

- `path:<path or glob>`: repo-relative, no spaces. Ok when it matches a file, else stale.
- `cmd:<manifest>#<name>`: `package.json` script or `Makefile` target. Ok when the name exists, else stale; other manifests are unverifiable.
- `correction:<YYYY-MM-DD> <text>`: a dated user correction. Unverifiable, never stale.

Untyped text is unverifiable. A bad date or an empty value is malformed.

## Trigger

- `always`, or no trigger: loads for every task.
- `paths:<glob>[, <glob>]`: loads when a task path or changed file matches a glob. `*` and `?` stay within one directory, `[abc]`, `[a-z]` and `[!abc]` match one character, `**` crosses directories; a bare directory means everything under it. A leading `./` is ignored. A literal `[` is written `[[]`; an existing path also matches as written.
- `kind:<k>[, <k>]`: `research`, `build` or `review`; loads for that task kind. The default path is `build`.

A malformed trigger (or a glob over 200 chars) loads always and doctor reports it.

## Writing

Add a bullet under the matching `##`, or replace exactly one line. Never rewrite a file; an annotation never adds a line. Prefer `path` or `cmd` when a file or script backs the rule, else `correction` dated today.

## Examples

```
- Hooks exit 0 on a missing dependency | evidence: path:plugin/hooks/*.sh
```

```
- Run the suite with make test | evidence: cmd:Makefile#test
```

```
- Use tabs in Go files | evidence: correction:2026-10-11 reviewer asked twice | applies when: paths:src/**/*.go
```

```
- Docs name the file they describe | applies when: kind:research, review
```

Check: `python3 ${CLAUDE_PLUGIN_ROOT}/skills/task-assets/assets/rules-check.py [--select PATH... --kind K]`
