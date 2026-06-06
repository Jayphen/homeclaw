---
id: TASK-35
title: Stop routine outputs entering LLM history
status: Done
assignee:
  - '@me'
created_date: '2026-06-06 07:22'
updated_date: '2026-06-06 07:24'
labels: []
dependencies: []
priority: high
ordinal: 35000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Scheduled and manually triggered routines currently use normal AgentLoop history, so previous routine outputs are included in future routine prompts. Add a non-persistent/no-history execution path for CallType.ROUTINE uses from the scheduler while retaining routine result storage for UI display.
<!-- SECTION:DESCRIPTION:END -->
