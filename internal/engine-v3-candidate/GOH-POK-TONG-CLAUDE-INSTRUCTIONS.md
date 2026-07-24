# GOH POK TONG — CLAUDE CODE INSTRUCTIONS

## Package
This is one clean package. No nested ZIP. This is the only instruction file.

Files: `engine.js`, `advanced-engine.js`, tests, rules, fixtures, methodology, and `package.json`.

Status: **0.3.0 strongest responsible candidate — UNVALIDATED**. No runtime AI is required.

## Step 1 — Put it in the repository
Extract this package to `internal/engine-v3-candidate/` inside the approved Goh Pok Tong repository. Create a Git checkpoint and branch before changes.

```bash
git add -A
git commit -m "Checkpoint approved Goh Pok Tong before engine v3"
git switch -c feature/bazi-engine-v3
```

## Step 2 — Ask Claude to ingest only
Paste this exact prompt:

```text
Read the complete approved Goh Pok Tong repository and every file under internal/engine-v3-candidate/. Start with GOH-POK-TONG-CLAUDE-INSTRUCTIONS.md.

Inspection only. Do not modify, create, move, delete, or install anything. Do not redesign the UI.

Return: (1) repository structure, (2) current birth-data-to-Four-Pillars flow, (3) solar-term logic, (4) timezone and True Solar Time handling, (5) current reading flow, (6) exact analyseAdvanced() integration point, (7) normalized pillar adapter mapping, (8) duplicate/conflicting calculations, (9) files proposed for change, (10) UI preservation approach, (11) feature flag, (12) tests and rollback, (13) limitations, and (14) blockers.

Do not call the engine validated, accurate, scientific, or practitioner-grade.
```

Accept ingestion only if Claude identifies one pillar-calculation source of truth, a precise adapter, a feature flag, UI preservation, zero runtime AI, tests, and rollback.

## Step 3 — Ask Claude to integrate
Paste only after accepting the ingestion report:

```text
Proceed with controlled integration.

Preserve the approved UI and default behavior. Put runtime engine files in a modular folder. Create one adapter from the application's existing pillars; do not create a second pillar calculator. Run analyseAdvanced() only under a development feature flag such as ?engine=v3. Keep the current reading as default. Use no runtime AI API. Change no coefficient or rule without documentation.

Add a development-only evidence panel with normalized pillars, hidden stems, element and Ten Gods scores, strength evidence and roots, branch relationships, Three Harmony/Meeting signals, Useful Element method statuses, candidate structure, matched rules, engine version, UNVALIDATED status, and limitations.

Never treat a detected combination as completed transformation without documented support. Do not invent expected practitioner conclusions. Run npm run test:all and all existing application tests.

Return files changed, adapter mapping, full test results, UI comparison, assumptions, unresolved gaps, and rollback command. Do not create a deployment ZIP yet.
```

## Step 4 — Ask Claude to audit

```text
Audit the engine-v3 integration and fix defects only. Check duplicated pillar calculation; solar-term/timezone/True Solar Time regressions; unsupported transformation; invented Useful Element resolution; unlabelled heuristics; rules embedded in UI; runtime AI calls; secrets; evidence panel visible by default; UI regression; feature-flag bypass; meaningless tests; unreviewed fixtures counted as validation; and missing UNVALIDATED status.

Return findings, fixes, final tests, limitations, and GO or NO-GO for deployment packaging.
```

## Step 5 — Ask Claude to package
Only after a GO:

```text
Create one deployment candidate ZIP from the audited integrated repository. Do not deploy or push.

Preserve default production behavior and keep engine v3 behind the feature flag. Include required runtime files. Exclude .git, node_modules, caches, secrets, environment files, screenshots, temporary files, and obsolete archives. Preserve existing hosting/build architecture; add no server, database, paid API, or new platform.

Generate the deployment ZIP, SHA-256 checksum, DEPLOYMENT-README.md, RELEASE-NOTES.md, TEST-REPORT.md, and ROLLBACK.md. State package version, Git commit, build/test commands and results, included/excluded files, flag behavior, rollback commit, and known limitations. Do not claim validated or guaranteed accuracy. Return artifact path and checksum.
```

## Acceptance checklist
- Existing UI/default reading preserved
- Engine v3 disabled by default and activated only by flag
- One pillar source of truth
- No runtime AI
- Evidence hidden by default
- `npm run test:all` passes
- No unsupported transformation or Useful Element claim
- UNVALIDATED status remains
- Deployment checksum and rollback exist
