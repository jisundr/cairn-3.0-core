---
name: review-pr
description: Reviews a PR/MR with code-review findings, cairn's security checklist and fix-lane tags. Posts only on confirmation.
---

# cairn:review-pr

## Resolve the target

Host from the URL (`github.com` → `gh`, a GitLab host → `glab`). Neither CLI resolves, or isn't authenticated for that host → report and point at that CLI's own login command, stop.

## Mode detection

Read the PR/MR's existing comments/discussions. Carries a `## Finding N` heading (or equivalent) from a prior run of this skill → Re-review. Otherwise → First review. The caller names Final review explicitly (e.g. "let's do the final pass") rather than this being auto-detected.

## Reference

| File | Load when |
|---|---|
| reference/draft-template.md | Drafting findings (First review step 3) or round replies (Re-review step 3) — format, on-disk path, and how to post. |

## First review

**Code Review**
1. Run `Skill(skill: "code-review", args: "<target>")` for the full correctness/reuse/simplification/efficiency pass — no `--comment`, so nothing posts yet.
2. Load `Skill(skill: "cairn:shared")`; check the diff against `reference/security-checklist.md` (Critical/High fails the review) and tag step 1's reuse/simplification/efficiency findings with `reference/fix-lanes.md`'s Lane A/B — classification only.

**Create Review Draft**

3. Write the combined findings as a draft, per `reference/draft-template.md` (format and on-disk path).

**Post (if allowed) or Edit**

4. `AskUserQuestion`: **Post** or **Edit**.
   - Edit → fold in feedback, back to step 3, ask again — no round limit.
   - Post → post via `gh`/`glab` (host above). A CLI auth/permission error means it's not allowed: report it and hand over the draft as final text to post manually instead of retrying.
5. Offer to keep monitoring the MR going forward. Declining is a clean no-op — no watcher, no state left behind.

## Re-review

**Code Review**
1. For each prior finding, diff the current code against it: `fixed` / `partially-fixed` / `still-open` / `disputed`.
2. Rerun First review's Code Review steps 1–2, scoped to what changed since the last round, to catch anything new.

**Update Review Draft**

3. Append a dated round section to the same on-disk draft: a reply per prior finding (ack fixes, hold open what isn't) plus any new finding from step 2, in the template's round format — each finding keeps its `Posting plan` line (new top-level comment/discussion vs. reply to thread #n).

**Post or Reply or Edit**

4. `AskUserQuestion`: **Post**, **Reply**, or **Edit** (a round can need both; do both when present, else ask again for what's left).
   - Edit → fold in feedback, back to step 3, ask again.
   - Post → findings marked "new top-level comment/discussion" go as one round-summary comment via `gh`/`glab`.
   - Reply → findings marked "reply to thread #n" go as individual thread replies via `gh`/`glab`.
   - Same auth/permission fallback as First review's Post branch.

## Final review + manual QA

1. Rerun First review's steps 1–2, scoped to what's changed since the last round, to catch regressions the fixes may have introduced.
2. Clean → `Skill(skill: "cairn:run")` to launch the app. Unavailable or fails to start → report it, ask the user to confirm manual QA is otherwise covered; don't block approval on it. Not clean → draft the new finding(s) as a fresh round and loop back to Re-review's assessment step, same as a QA-reported problem in step 3.
3. Hand off for human manual QA. A reported problem loops back to Re-review's assessment step rather than starting over.

## Approval + cleanup

1. Stop whatever Final review's `cairn:run` started.
2. Approve the MR and post a final summary comment, using the merge method / push-safety convention from `workflow.md`'s `## Commits / PR`. Convention undocumented → ask once; never guess a merge command.
3. The draft file is gitignored; report its path — nothing else to clean up.
4. Report done.
