---
id: TASK-38
title: Prevent semantic recall backend errors from crashing chat
status: Done
assignee:
  - '@me'
created_date: '2026-06-10 06:45'
updated_date: '2026-06-10 06:47'
labels: []
dependencies: []
priority: high
ordinal: 37000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Chat requests can fail when memsearch search reaches Milvus Lite hybrid_search and raises MilvusException(function_score). Semantic recall is optional Layer 2 memory, so recall errors should be logged and degrade to empty results instead of bubbling through build_context and /api/chat.
<!-- SECTION:DESCRIPTION:END -->
