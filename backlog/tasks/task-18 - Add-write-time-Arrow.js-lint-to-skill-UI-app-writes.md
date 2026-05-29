---
id: TASK-18
title: Add write-time Arrow.js lint to skill UI-app writes
status: To Do
assignee: []
created_date: '2026-05-29 05:32'
labels:
  - arrow-js
  - skills
  - dx
dependencies: []
priority: medium
ordinal: 18000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Subtly-wrong Arrow apps fail silently (blank/stale UI, no surfaced console error), and the only feedback loop is the optional browser_enabled web_browse check — so the agent has no signal it is close and reverts to plain HTML/CSS. When skill_enable_ui_app or skill_edit_file writes an assets/*.html, run a lightweight lint that returns warnings the agent must address for the known footguns: (a) on*="${...}" event attributes (onclick/oninput/onchange) instead of @event; (b) likely-non-reactive ${state.x} (bare member access without an arrow) inside an html` template; (c) imports of @arrow-js/framework or use of render(/boundary(/renderToString( in a no-build mini-app; (d) missing html`...`(mountEl) mount call. Warnings only (do not block writes), surfaced in the tool result so the agent self-corrects.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 skill_enable_ui_app and skill_edit_file run the lint on assets/*.html writes
- [ ] #2 Lint flags on*-attribute handlers, non-reactive interpolations, framework imports, and missing mount
- [ ] #3 Findings are returned as warnings in the tool result (non-blocking); unit tests cover each rule
<!-- AC:END -->
