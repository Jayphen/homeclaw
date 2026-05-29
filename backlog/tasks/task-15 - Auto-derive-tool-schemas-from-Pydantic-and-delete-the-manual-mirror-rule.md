---
id: TASK-15
title: Auto-derive tool schemas from Pydantic and delete the manual-mirror rule
status: To Do
assignee: []
created_date: '2026-05-29 05:02'
labels:
  - tier-4
  - typing
  - agent
dependencies:
  - TASK-3
priority: low
ordinal: 15000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
tool_decorator.py already auto-derives tool schemas from type hints, so the CLAUDE.md 'manually mirror the Pydantic model' rule is mostly fiction. Add one branch to _type_to_schema: BaseModel -> model_json_schema(), and dict[str,X] -> additionalProperties. Define InitialFile/BookmarkSource models for skill_create and type those params with them — this deletes the 28-line hand-written schema_overrides block AND adds boundary validation of currently-unchecked dict indexing (f['filename'] at tools.py:1629). Then remove the manual-sync rule from CLAUDE.md.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 _type_to_schema handles BaseModel and dict[str,X]; skill_create schema_overrides deleted
- [ ] #2 InitialFile/BookmarkSource models added and validated at the boundary
- [ ] #3 CLAUDE.md 'tool schemas must mirror the Pydantic models' rule removed; tests pass
<!-- AC:END -->
