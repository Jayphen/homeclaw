---
id: TASK-5
title: Split Settings.svelte into per-tab panel components
status: To Do
assignee: []
created_date: '2026-05-29 05:01'
labels:
  - tier-2
  - decomposition
  - ui
dependencies: []
priority: medium
ordinal: 5000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Settings.svelte (2297 lines) is six pages welded together: ~55 independent $state vars across unrelated domains. Split along existing tab boundaries into ProviderPanel, ChannelsPanel, GeneralPanel, MembersPanel, DataPanel, ToolLogPanel (under ui/src/lib/settings/), leaving a ~120-line shell that owns only tab nav + page state + error card. The log viewer (~350 lines) is a strong candidate for its own LogViewer.svelte.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Settings.svelte reduced to a thin shell; one component per tab
- [ ] #2 No behavior/markup regressions; each panel owns its own state
<!-- AC:END -->
