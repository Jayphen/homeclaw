---
id: TASK-33
title: Reduce live chat history prompt budget
status: Done
assignee:
  - '@me'
created_date: '2026-06-06 07:11'
updated_date: '2026-06-06 07:13'
labels: []
dependencies: []
priority: high
ordinal: 33000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Debug UI shows chat requests still include 200 messages and roughly 29k estimated history tokens. Add a smaller live-history target and expose the target/threshold in debug metadata so prompt size drops immediately while append-only history remains available for consolidation.
<!-- SECTION:DESCRIPTION:END -->
