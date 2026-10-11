---
name: fix-lanes
description: Lane A/B tags for a diff review's own reuse, simplification, and efficiency findings — classification only, to speed up human triage.
---

# Fix lanes

Applies to the reuse/simplification/efficiency findings a diff review already surfaces — not to security-checklist findings, which carry a severity instead (a security fix is a judgment call by nature, never mechanical).

| Lane | Meaning |
|---|---|
| A | Mechanical, behavior-preserving — renames, dead-code removal, magic-number extraction, pure duplicate-logic extraction with no signature change. |
| B | Behavior-changing or judgment-dependent — anything that changes a signature, a public interface, or program behavior. |

**Unsure → Lane B.**

Classification only: no cairn artifact auto-applies a fix under either lane today. The tag exists so a human scanning the findings draft can tell what's likely safe to accept quickly from what needs a real look — it authorizes nothing on its own.
