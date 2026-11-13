# Security policy

Report suspected vulnerabilities or credential exposure privately to the repository owner via an established contact channel. Do not include secrets or confidential test data in public issues, pull requests, or logs.

## Repository safeguards

- Use least-privilege, short-lived credentials and MFA/passkeys. Never store live credentials, private keys, seed phrases, or unredacted production/test data in Git.
- Changes to default branches, CI configuration, deployment scripts and security controls must be reviewed. CODEOWNERS requests ownership review; it is not an enforced rule by itself.
- Use protected default/release branches, prohibit force pushes and deletion, require PR review and successful security checks where supported. GitHub settings must be configured separately by an administrator.
- The security guard scans changed files for selected credential formats and risky workflow patterns. It runs with read-only contents permission, no user secrets, and SHA-pinned checkout. It is not full-history secret scanning and is not a replacement for an enforced ruleset or independent review.
- Keep production secrets scoped to a protected deployment environment; do not approve unverified deployment commits. Never enable paid API use or release/deployment solely as part of a security check.
- If compromise is suspected: preserve evidence, pause deployments, revoke affected credentials at the issuer, verify account sessions and integrations, and compare Git history against trusted copies. Do not delete evidence.
