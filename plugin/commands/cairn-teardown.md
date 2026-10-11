---
description: Removes cairn's marker and .cairn/, and reports what stays and why.
---

1. If `CLAUDE.md` contains the `<!-- cairn:start -->` … `<!-- cairn:end -->` block, remove it and collapse the leftover blank line. If absent, say so.
2. If `.cairn/` exists, remove it. If absent, say so.
3. Report what was left and why: `.harness/`, `docs/tasks/` and any `CLAUDE.md` line pointing at `.harness/` are the project's own content, so the rules keep working without cairn; `.harness/local/` is the developer's own. None of these are touched.
4. Point at `/plugin uninstall` for removing the plugin itself — this command only undoes what `/cairn-setup` wrote.
