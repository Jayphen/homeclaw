---
id: TASK-7
title: Split skills loader.py into models/frontmatter/env/plugin/discovery
status: To Do
assignee: []
created_date: '2026-05-29 05:01'
labels:
  - tier-2
  - decomposition
  - plugins
dependencies: []
priority: medium
ordinal: 7000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
homeclaw/plugins/skills/loader.py (996 lines) mixes five cohesive concerns already separated by comment banners. Split into skills/models.py, skills/frontmatter.py, skills/env.py, skills/plugin.py (the SkillPlugin class), skills/discovery.py. Lowest-risk first: frontmatter + env are pure functions the API layer already reaches into via private symbols — extracting them fixes that leak.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 loader.py split into the five modules; no private-symbol imports from the API layer remain
- [ ] #2 Tests + typecheck pass; skill loading behavior unchanged
<!-- AC:END -->
