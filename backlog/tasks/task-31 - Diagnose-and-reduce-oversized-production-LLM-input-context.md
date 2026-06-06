---
id: TASK-31
title: Diagnose and reduce oversized production LLM input context
status: Done
assignee:
  - '@me'
created_date: '2026-06-06 06:36'
updated_date: '2026-06-06 06:40'
labels: []
dependencies: []
priority: high
ordinal: 31000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Production calls are using roughly 115k input tokens. Investigate consolidation thresholds/pointer advancement and add diagnostics/fixes so unconsolidated history does not remain in prompt indefinitely.
<!-- SECTION:DESCRIPTION:END -->
