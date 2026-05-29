---
id: TASK-16
title: 'Ship a correct, tracked Arrow.js reference mini-app'
status: Done
assignee:
  - '@me'
created_date: '2026-05-29 05:32'
updated_date: '2026-05-29 06:00'
labels:
  - arrow-js
  - skills
  - dx
dependencies: []
priority: high
ordinal: 16000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
There is no tracked/shipped Arrow.js example app — the only 'demo' is whatever each instance's LLM hand-generates locally, and it gets the API wrong (the local gitignored workspaces/household/skills/demo-counter used plain onclick= instead of Arrow's @click, so its buttons fired inc()/dec()/reset() at render and did nothing on click). Ship a canonical, correct, interactive reference mini-app in the repo (tracked, e.g. under plugins/ or a skills seed) that the agent can install/copy as a known-good starting point. It must demonstrate: @click event binding, reactive ${() => state.x} vs static, html`...`(el) mount, auth token from localStorage, and a SELECT-only db/query fetch. Keep it tiny and self-contained.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A correct interactive Arrow mini-app ships in a tracked repo location (not gitignored workspaces)
- [x] #2 It uses @click (not onclick), reactive function expressions, and the html`...`(el) mount idiom
- [x] #3 skill-creator guidance points the agent at this app as the canonical example to copy
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Shipped homeclaw/skills/skill-creator/assets/reference-mini-app.html — a tracked, self-contained, browser-verified Arrow mini-app. Demonstrates: @click (not onclick), reactive ${() => x} vs static, html`...`(el) mount, auth token from localStorage, SELECT-only db/query fetch, keyed lists, and loading/error/empty states. Heavily commented with what to change when copying (owner/name in API paths, SQL + columns, markup).

Verified in a real browser (Chrome): served a mock-data copy over http, drove real .click() on the filter buttons, and confirmed @click fires -> reactive state mutates -> DOM reactively re-renders (count 3of3 -> 2of3 -> 1of3, list filters, active class moves). No console errors on load. (Note: Arrow batches DOM updates on a microtask, so a synchronous read right after .click() shows stale DOM — must await a tick to observe the flush.) Fetch path matches the verified db/query endpoint contract in api/routes/skills.py (POST {sql}; returns {rows,count}; Bearer auth).

AC#3: SKILL.md now names this file as the canonical 'copy this, don't write from scratch' starting point, with the exact skill_edit_file read command and what to change.

Packaging: hatchling has no custom build config, so all files under homeclaw/ ship by default (same mechanism as references/*.md). read_skill lists assets/ in resources, so the agent discovers it. typecheck 0 errors, ruff clean, 648 tests pass.
<!-- SECTION:NOTES:END -->
