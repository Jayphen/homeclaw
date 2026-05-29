---
id: TASK-30
title: 'Cleanup: retire the iframe asset path and token-in-URL once sandbox apps ship'
status: In Progress
assignee:
  - '@me'
created_date: '2026-05-29 11:37'
updated_date: '2026-05-29 15:41'
labels:
  - skills
  - security
  - cleanup
dependencies:
  - TASK-28
priority: medium
ordinal: 30000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Remove the obsolete HTML-iframe mini-app machinery after the sandbox path is live.

Changes:
- Remove assets/index.html iframe serving for mini-apps + the ?token= query-param auth (deps.py _parse_auth query branch, skillAppSrc in ui/src/lib/api.ts).
- Remove the detail-page iframe embed in Skills.svelte and the render-boundary HTML injection in skills.py (superseded by sandbox onError).
- Keep db/query + db/schema (used by the host bridge). Audit for any remaining URL-token usage.

Depends on TASK-28 (sandbox rendering must be live first).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 ?token= query-param auth and skillAppSrc removed; session token never in a URL
- [x] #2 iframe asset serving + render-boundary HTML injection removed; db endpoints retained
- [x] #3 no remaining URL-token usage (verified)
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Removed token-in-URL and the iframe machinery: deps.py _parse_auth no longer accepts ?token= (header Bearer only); skillAppSrc deleted from api.ts; serve_skill_asset + the injected HTML error boundary (_RENDER_BOUNDARY_* / _inject_render_boundary) removed from skills.py; AppView iframe branch + 'Open in tab' removed (sandbox-only; legacy-kind shows a 'rebuild as sandbox' notice); Skills.svelte detail iframe panel replaced with an 'Open app' link to /apps. Retained the render-log feedback loop (post_render_log + skill_render_status) and rewired it — AppView now POSTs sandbox onError to /_render_log so skill_render_status still works. arrow_lint kept (still used by skill_edit_file for legacy assets/*.html). Tests: dropped boundary-injection + asset-injection tests; kept render-log/schema/app-source. 701 tests pass; typecheck + lint clean; ui build OK. Verified: no ?token=, no skillAppSrc, no serve_skill_asset, no iframe remain.
<!-- SECTION:NOTES:END -->
