---
id: TASK-40
title: Cap semantic memory dependency minor versions
status: Done
assignee:
  - '@me'
created_date: '2026-06-10 07:18'
updated_date: '2026-06-10 07:18'
labels: []
dependencies: []
priority: high
ordinal: 39000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Production installs the semantic extra via pip from pyproject.toml, so uv.lock alone cannot prevent future incompatible memsearch/pymilvus/milvus-lite combinations. Cap the compatible minor lines for the semantic stack.
<!-- SECTION:DESCRIPTION:END -->
