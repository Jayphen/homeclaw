---
id: TASK-16
title: 'Ship a correct, tracked Arrow.js reference mini-app'
status: To Do
assignee: []
created_date: '2026-05-29 05:32'
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
- [ ] #1 A correct interactive Arrow mini-app ships in a tracked repo location (not gitignored workspaces)
- [ ] #2 It uses @click (not onclick), reactive function expressions, and the html`...`(el) mount idiom
- [ ] #3 skill-creator guidance points the agent at this app as the canonical example to copy
<!-- AC:END -->
