---
id: TASK-11
title: Unify skill .env handling into a single skills/env module
status: To Do
assignee: []
created_date: '2026-05-29 05:02'
labels:
  - tier-3
  - duplication
  - plugins
dependencies:
  - TASK-7
priority: low
ordinal: 11000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
There are three independent .env parsers with different rules: loader.py:307 _load_skill_env (strips quotes), skills.py:44 _parse_env (does not strip), and the inline write/merge at skills.py:559-585. Values round-trip inconsistently between write and runtime read. Make skills/env.py the single source: read_env()->dict, write_env(entries), mask_env(). Collapse the route helpers and inline write block onto it.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 One env module owns read/write/mask; route + loader + runtime all use it
- [ ] #2 Quote handling is consistent across write and read; tests cover round-trip
<!-- AC:END -->
