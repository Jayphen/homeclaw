---
id: TASK-39
title: Align Milvus Lite dependency with PyMilvus hybrid search protocol
status: Done
assignee:
  - '@me'
created_date: '2026-06-10 07:12'
updated_date: '2026-06-10 07:15'
labels: []
dependencies: []
priority: high
ordinal: 38000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The semantic stack currently resolves pymilvus 2.5.18 with milvus-lite 2.5.1. PyMilvus hybrid_search sends/uses function_score, but Milvus Lite 2.5.1 does not expose that request field, causing MilvusException(function_score). Force a compatible Milvus Lite version and refresh the lockfile so semantic recall works instead of falling back.
<!-- SECTION:DESCRIPTION:END -->
