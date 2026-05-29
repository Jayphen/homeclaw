---
id: TASK-23
title: Add Apps launcher page and per-app routes for skill mini-apps
status: Done
assignee:
  - '@me'
created_date: '2026-05-29 10:13'
updated_date: '2026-05-29 10:42'
labels:
  - ui
  - skills
  - mini-app
dependencies: []
priority: high
ordinal: 23000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Introduce a first-class Apps section in the web UI that collects every skill exposing a ui_app and gives each its own deep-linkable route, instead of the cramped iframe panel buried in the skill-detail page.

Routes:
- /apps — launcher listing all skills whose detail has a ui_app entry; each card links to its full view
- /apps/{owner}/{name} — full-bleed Svelte wrapper view that hosts the mini-app mount

This slice is UX/navigation only — it still renders the existing iframe (same sandbox/token as today). Hardening the mount (opaque origin, scoped capability token, postMessage) is split into the follow-up tasks so this lands independently. Wire routes in App.svelte via svelte-spa-router and add nav entry.

Files: ui/src/App.svelte (routes + nav), new ui/src/views/Apps.svelte (launcher), new ui/src/views/AppView.svelte (per-app wrapper), reuse appSrc() from Skills.svelte for now.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 /apps route lists every skill that has a ui_app entry, with links to each app's full view
- [x] #2 /apps/{owner}/{name} renders the mini-app full-bleed in a normal app route (no skill-detail chrome)
- [x] #3 Routes wired in App.svelte and reachable from app navigation
- [x] #4 Existing skill-detail iframe behaviour unchanged; no regression to current token/sandbox handling
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Code-complete and compiling (vite build clean, no warnings from new files).

Changes:
- ui/src/lib/api.ts: extracted skillAppSrc(owner,name,entry) as the single source of truth for mini-app iframe URLs (incl. ?token=); documented its planned removal under TASK-25/26.
- ui/src/views/Apps.svelte (new): launcher — fetches /api/skills, filters to entries with ui_app, renders a card grid linking to #/apps/{owner}/{name}; loading/error/empty states.
- ui/src/views/AppView.svelte (new): full-bleed per-app wrapper — fetches detail, renders the iframe filling the content area with a header bar (back, title, owner tag, Manage skill, Open in tab). Reuses skillAppSrc; sandbox/token unchanged from the detail-page embed (hardening is TASK-24/25).
- ui/src/views/Skills.svelte: now imports skillAppSrc (removed local appSrc + unused getToken import); detail-page embed behaviour unchanged.
- ui/src/App.svelte: routes /apps and /apps/:owner/:name wired; 'Apps' added to primary nav.

Verification: vite build passes; new files emit no compiler/a11y warnings. Live happy-path render not exercised — no household config or installed mini-app skill present locally, and seeding workspace state was out of scope for this slice.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Shipped in PR #164 (squash-merged to main as a3ce7f5). Apps launcher (/apps) + full-bleed per-app routes (/apps/{owner}/{name}); skillAppSrc extracted to $lib/api; Apps to primary nav. Sandbox/token unchanged this slice — hardening continues in TASK-24/25/26. vite build clean.
<!-- SECTION:FINAL_SUMMARY:END -->
