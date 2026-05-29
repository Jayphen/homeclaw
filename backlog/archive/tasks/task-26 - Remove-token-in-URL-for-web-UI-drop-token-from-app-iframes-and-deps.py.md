---
id: TASK-26
title: Remove token-in-URL for web UI (drop ?token= from app iframes and deps.py)
status: To Do
assignee: []
created_date: '2026-05-29 10:14'
updated_date: '2026-05-29 11:37'
labels:
  - ui
  - skills
  - security
dependencies: []
priority: medium
ordinal: 26000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Once mini-apps authenticate via the postMessage capability token (TASK-25), remove the token-in-URL path entirely so the 7-day session JWT never appears in any URL (it leaks via access logs, history, Referer).

Changes:
- Delete the ?token= construction in appSrc() (ui/src/views/Skills.svelte:367) and any remaining callers.
- Remove the ?token= query-param branch in _parse_token / the request auth path (homeclaw/api/deps.py:321-324) after confirming no remaining consumer (downloads, etc.).
- Audit for any other URL token usage (downloads, QR, asset links) and migrate or document.

Files: ui/src/views/Skills.svelte, homeclaw/api/deps.py.

Depends on TASK-25.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 appSrc() no longer appends ?token=; no UI code puts the session token in a URL
- [ ] #2 deps.py query-param token branch removed and no endpoint relies on it (verified)
- [ ] #3 Any other URL-token usages identified and migrated or explicitly documented
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
SUPERSEDED by the @arrow-js/sandbox adoption arc (TASK-27..30). The iframe + scoped-capability-token approach is obsolete: Arrow's WASM sandbox gives stronger isolation rendered inline, with no iframe and no tokens (host mediates all data via hostBridge). Verified by spike on branch spike/arrow-sandbox.
<!-- SECTION:NOTES:END -->
