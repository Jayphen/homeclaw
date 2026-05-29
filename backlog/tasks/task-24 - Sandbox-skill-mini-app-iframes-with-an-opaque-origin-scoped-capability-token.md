---
id: TASK-24
title: Sandbox skill mini-app iframes with an opaque origin + scoped capability token
status: To Do
assignee: []
created_date: '2026-05-29 10:14'
labels:
  - ui
  - skills
  - mini-app
  - security
dependencies:
  - TASK-23
priority: high
ordinal: 24000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Make the per-app route's iframe a real isolation boundary. Today it is sandbox='allow-scripts allow-same-origin allow-forms' served same-origin, so the mini-app shares the SPA realm: it can read homeclaw_token from localStorage and call the full API. Skills are untrusted third-party code (installable from arbitrary GitHub URLs/gists), so this must not share the realm.

Changes:
- Drop allow-same-origin from the iframe sandbox -> the frame gets a unique opaque origin even though served from /api/skills/.../assets/. No parent localStorage/DOM access.
- Add POST /api/skills/{owner}/{name}/app-token returning a short-lived (minutes), narrowly-scoped capability token bound to the CURRENT viewer + that skill's data namespace + SELECT-only db.
- Enforce that scope server-side: db/query and db/schema accept the capability token (via header) and restrict to the scoped namespace; reject the session JWT used out of scope.
- CORS: allow Origin: null (opaque-origin frame) for the skill asset + db endpoints.

Files: ui/src/views/AppView.svelte (sandbox attr), homeclaw/api/deps.py (capability token mint/parse + scope), homeclaw/api/routes skills.py (app-token endpoint, db/query + db/schema scope enforcement, CORS).

Depends on TASK-23 (route must exist first). postMessage delivery of the token is TASK-25.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Per-app iframe uses sandbox without allow-same-origin (opaque origin); cannot read parent localStorage or DOM
- [ ] #2 POST app-token endpoint mints a short-lived token scoped to the viewer + skill namespace + SELECT-only db
- [ ] #3 db/query and db/schema enforce the capability token's scope server-side
- [ ] #4 Opaque-origin (Origin: null) requests to skill asset + db endpoints handled via CORS
<!-- AC:END -->
