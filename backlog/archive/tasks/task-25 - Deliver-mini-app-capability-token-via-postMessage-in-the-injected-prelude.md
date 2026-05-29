---
id: TASK-25
title: Deliver mini-app capability token via postMessage in the injected prelude
status: To Do
assignee: []
created_date: '2026-05-29 10:14'
updated_date: '2026-05-29 11:37'
labels:
  - ui
  - skills
  - mini-app
  - security
dependencies: []
priority: high
ordinal: 25000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Move token handling out of the URL and into the auto-injected homeclaw-app.js prelude (the same prelude that already adds the error boundary in PR #162). The parent route postMessages the scoped capability token to the iframe on load; the prelude receives it, holds it in memory (opaque origin cannot use localStorage), and provides an authenticated fetch wrapper so skill authors keep writing a plain db/query call.

Changes:
- Parent AppView.svelte: on iframe load, fetch the app-token (TASK-24) and postMessage it to iframe.contentWindow with an explicit targetOrigin.
- Injected prelude (homeclaw-app.js / skills.py injection): listen for the homeclaw:token message, store in a closure, expose an authenticated fetch/helper that attaches the token header; queue calls until the token arrives.
- Update reference-mini-app.html + skill-creator SKILL.md to drop any manual token/URL handling and use the provided helper.

Files: homeclaw/api/skills.py (prelude injection), homeclaw/skills/skill-creator/assets/reference-mini-app.html, homeclaw/skills/skill-creator/SKILL.md, ui/src/views/AppView.svelte.

Depends on TASK-24.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Capability token is delivered to the iframe via postMessage with an explicit targetOrigin (never the URL)
- [ ] #2 Injected prelude receives the token, holds it in memory, and authenticates db/query + db/schema calls transparently
- [ ] #3 Reference mini-app and SKILL.md updated to drop manual token handling
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
SUPERSEDED by the @arrow-js/sandbox adoption arc (TASK-27..30). The iframe + scoped-capability-token approach is obsolete: Arrow's WASM sandbox gives stronger isolation rendered inline, with no iframe and no tokens (host mediates all data via hostBridge). Verified by spike on branch spike/arrow-sandbox.
<!-- SECTION:NOTES:END -->
