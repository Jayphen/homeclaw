---
id: TASK-6
title: Split Skills.svelte and componentize Dashboard.svelte
status: To Do
assignee: []
created_date: '2026-05-29 05:01'
labels:
  - tier-2
  - decomposition
  - ui
dependencies: []
priority: low
ordinal: 6000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Skills.svelte (1031 lines) is a mode-switched mega-view: split into SkillIndex/SkillDetail/SkillFileView (+ SkillArchives, DepWarnings reused). Dashboard.svelte (1029 lines) repeats the same card-with-list shape 8x and re-declares Card/Badge CSS: extract Card.svelte + Badge.svelte and a KnowledgeMember.svelte (rendered twice today).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Skills.svelte split along its {#if mode} seams
- [ ] #2 Dashboard card sections use shared Card/Badge components; duplicated knowledge-member block deduped
<!-- AC:END -->
