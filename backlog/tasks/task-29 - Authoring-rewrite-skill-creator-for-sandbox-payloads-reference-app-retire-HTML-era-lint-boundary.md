---
id: TASK-29
title: >-
  Authoring: rewrite skill-creator for sandbox payloads + reference app; retire
  HTML-era lint/boundary
status: To Do
assignee: []
created_date: '2026-05-29 11:37'
labels:
  - skills
  - mini-app
  - sandbox
  - docs
dependencies:
  - TASK-28
priority: medium
ordinal: 29000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Move skill mini-app authoring from single-HTML to sandbox source payloads.

Changes:
- Rewrite skill-creator SKILL.md mini-app guidance to produce a source object (main.ts/main.css). Adopt Arrow's official create_arrow_sandbox tool schema + agent prompt (https://arrow-js.com) as the authoring contract.
- Ship a working reference sandbox mini-app (source-based) that uses the host db bridge.
- Retire/replace arrow_lint.py fatal-pattern rules and the auto-injected JS error boundary: the sandbox precompiles templates (errors surface via onError) so the blank-page failure mode and the HTML-comment/partial-attr footguns no longer apply the same way. Keep whatever still adds value.
- Update docs/ pages for the new mini-app model.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 skill-creator SKILL.md teaches the sandbox source-payload model (Arrow's tool schema + prompt)
- [ ] #2 A working source-based reference mini-app ships and uses the host db bridge
- [ ] #3 arrow_lint + injected error boundary reviewed: retired or re-scoped for the sandbox model; docs updated
<!-- AC:END -->
