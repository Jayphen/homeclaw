---
id: TASK-20
title: Add Arrow mini-app error boundary + runtime render-log feedback loop
status: Done
assignee: []
created_date: '2026-05-29 07:10'
updated_date: '2026-05-29 07:32'
labels: []
dependencies: []
ordinal: 20000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Locally-served prelude that renders thrown errors INTO the page (never blank) and POSTs runtime errors to a per-skill render-log endpoint the agent can read, so the agent self-corrects instead of using the user as test harness. No headless browser in the default image, so runtime signal comes from the user's own browser via the boundary.
<!-- SECTION:DESCRIPTION:END -->
