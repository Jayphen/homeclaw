---
id: TASK-21
title: Add skill DB schema discovery + stop swallowing db errors
status: Done
assignee: []
created_date: '2026-05-29 07:10'
updated_date: '2026-05-29 07:32'
labels: []
dependencies: []
ordinal: 21000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Add GET /api/skills/{owner}/{name}/db/schema (tables+columns) and a skill_db_schema agent tool so mini-apps are built against real columns. Update SKILL.md + reference app to surface db errors to state.error instead of silently rendering empty.
<!-- SECTION:DESCRIPTION:END -->
