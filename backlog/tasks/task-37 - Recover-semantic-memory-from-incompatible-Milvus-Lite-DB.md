---
id: TASK-37
title: Recover semantic memory from incompatible Milvus Lite DB
status: Done
assignee:
  - '@me'
created_date: '2026-06-10 06:24'
updated_date: '2026-06-10 06:26'
labels: []
dependencies: []
priority: high
ordinal: 36000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Startup currently logs Failed to initialize semantic memory when memsearch/pymilvus cannot open the local Milvus Lite .index/milvus.db file. Since the index is derived from workspace markdown/docs, quarantine the bad DB and rebuild automatically.
<!-- SECTION:DESCRIPTION:END -->
