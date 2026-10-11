---
name: security-checklist
description: Stack-agnostic security review categories with severity classification, for reviewer and review-pr to check a diff against alongside whatever it already covers.
---

# Security checklist

Adapted from maestro's `security-review-guide`, generalized: maestro's version hardcodes FastAPI/SQLAlchemy/React specifics; this stays at the pattern level so it holds for whatever stack the project's `architecture.md` names. Supplements the diff review already in progress — don't double-report a finding both here and under a standards.md/architecture.md citation.

## Severity

| Severity | Meaning | Result |
|---|---|---|
| Critical | Immediately exploitable — auth bypass, injection with unsanitized user input, plaintext/weakly-hashed secrets | Fail |
| High | Exploitable with moderate effort — missing authorization check, wildcard CORS with credentials, reflected XSS | Fail |
| Medium | Exploitable under specific conditions | Document only |
| Low | Minor hardening gap | Document only |

## Categories

1. **Authentication** — every route/handler that should require identity actually enforces it; session/token expiry is set and checked; no bypass via an alternate parameter or header.
2. **Authorization** — ownership is verified before returning or mutating a resource; no horizontal (another user's data) or vertical (elevated role) escalation; role/permission checks run server-side, never trusted from client-supplied data.
3. **Injection** — SQL, command, template, or query-language calls are parameterized; no string-built query or shell/`eval`-style call carries unsanitized user input.
4. **Input validation** — external input is type-, length-, and bounds-checked before use; file uploads validate type and size server-side, not by extension or client-supplied claim alone.
5. **Secrets exposure** — no hardcoded credential, key, or token in source, comments, or logs; secrets load from environment or a secret manager; example/config files hold only placeholders.
6. **Sensitive data handling** — passwords hashed with a modern algorithm, never plaintext or a broken hash; PII isn't written to logs; internal-only fields are excluded from external responses; error responses don't leak stack traces, queries, or paths.
7. **Security misconfiguration** — cross-origin config never combines a wildcard origin with credentials; allow-lists are explicit; no debug flag, test override, or auth bypass path ships to production.
8. **Output encoding / XSS** — user-supplied content renders as text or goes through an explicit sanitizer, never raw HTML; no dynamic code execution (`eval`, `new Function`, string-built shell) on user-controlled input; URLs are validated before use in a link or redirect.
9. **Dependency hygiene** — a dependency with a known critical vulnerability is flagged when the project already has a lockfile or audit tool named in the harness; this doesn't introduce new scanning tooling.

## Finding format

```
[file:line] Security [Severity]: <description>
Fix: <specific remediation>
```
