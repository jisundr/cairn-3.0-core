---
description: Cuts an rc tag or a final release via cairn:release.
argument-hint: rc|final [major|minor|patch|X.Y.Z]
---

Run `Skill(skill: "cairn:release", args: "$ARGUMENTS")`. No argument, or a first word other than `rc`/`final` → ask which, once.
