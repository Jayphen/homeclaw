---
id: TASK-28
title: >-
  Frontend: render skill mini-apps inline via @arrow-js/sandbox (lazy-loaded) +
  host db bridge
status: To Do
assignee: []
created_date: '2026-05-29 11:37'
labels:
  - ui
  - skills
  - mini-app
  - sandbox
  - security
dependencies:
  - TASK-27
priority: high
ordinal: 28000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Replace the iframe in AppView.svelte with an inline @arrow-js/sandbox mount. This is where the isolation win lands: untrusted mini-app code runs in a WASM VM with zero ambient authority (no localStorage/JWT, no direct fetch, host owns the DOM).

Changes:
- Add @arrow-js/sandbox dependency; LAZY-LOAD it via dynamic import() on the /apps/{owner}/{name} route only (keeps main bundle ~132KB gz; VM+compiler ~1.5MB loads on demand, cached).
- Fetch the skill source (TASK-27); render sandbox({source}, {output}, hostBridge) inline.
- hostBridge exposes a 'homeclaw' (or similar bare-specifier) module: db.query(sql,params) and db.schema() that call the EXISTING authenticated /db/query + /db/schema endpoints from the host (session token stays in the host realm; sandbox never sees it). Bare specifier only (no colon).
- Wire onError to a visible banner; handle output() (mutation intents) -> host performs authenticated writes, re-renders.

Note (spike findings): sandbox fails under Vite dev (WASM MIME) but works in production build; output is a VM global, not an import.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 AppView renders the mini-app inline via sandbox() — no iframe; @arrow-js/sandbox is lazy-loaded on the route
- [ ] #2 host db bridge (query/schema) calls the authenticated endpoints; sandbox has no token and no direct network
- [ ] #3 onError renders a visible banner; output() round-trips to the host
- [ ] #4 Realm isolation verified: mini-app cannot read localStorage / session token
<!-- AC:END -->
