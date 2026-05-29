---
id: TASK-28
title: >-
  Frontend: render skill mini-apps inline via @arrow-js/sandbox (lazy-loaded) +
  host db bridge
status: Done
assignee:
  - '@me'
created_date: '2026-05-29 11:37'
updated_date: '2026-05-29 15:16'
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
- [x] #1 AppView renders the mini-app inline via sandbox() — no iframe; @arrow-js/sandbox is lazy-loaded on the route
- [x] #2 host db bridge (query/schema) calls the authenticated endpoints; sandbox has no token and no direct network
- [x] #3 onError renders a visible banner; output() round-trips to the host
- [x] #4 Realm isolation verified: mini-app cannot read localStorage / session token
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
AppView renders sandbox apps (ui_app.kind=='sandbox') inline via @arrow-js/sandbox, lazy-loaded with dynamic import() so the VM+compiler (~1.5MB) only loads on the /apps route — main bundle stays 133KB gz (verified in build output). New $lib/sandbox.ts: fetchAppSource + mountMiniApp + a 'homeclaw' host bridge exposing query/schema that call the existing authenticated db endpoints from the host (session token never enters the VM). Legacy iframe apps still render via the old path. onError -> visible banner. Runtime-verified via throwaway harness (now removed): mountMiniApp mounts inline, bridge round-trips with Bearer token host-side, in-VM localStorage is undefined (isolation holds), rows render. svelte-check clean for AppView + sandbox.ts. Dev caveat: @arrow-js/sandbox needs the production build (Vite dev mis-serves the WASM); optimizeDeps.exclude added as best-effort.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Shipped in PR #167. Sandbox apps render inline via @arrow-js/sandbox (lazy-loaded), host 'homeclaw' bridge mediates db access (token stays host-side), runtime-verified isolation. Main bundle unchanged.
<!-- SECTION:FINAL_SUMMARY:END -->
