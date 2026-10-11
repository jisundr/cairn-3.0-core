# Refines, never overrides — this file may tighten a team standard; it may not relax, skip, or disable anything the team harness requires.
# No secrets — this is a preferences file, not an env file. No keys, tokens, or credentials.
# model <agent> = <model>[, <model>…] — models each role may use; the orchestrator picks within them. agent: builder/planner/reviewer/scribe/research; model: sonnet/opus/haiku/fable.
# model default = <model> — one model: for a role with no line of its own, and the no-signal pick within a list that includes it.
# prefer-path = default | escalated — biases cairn:start's path choice on a close call.
