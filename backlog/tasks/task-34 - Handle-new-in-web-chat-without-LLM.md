---
id: TASK-34
title: Handle /new in web chat without LLM
status: Done
assignee:
  - '@me'
created_date: '2026-06-06 07:15'
updated_date: '2026-06-06 07:16'
labels: []
dependencies: []
priority: high
ordinal: 34000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The web chat currently sends /new to the model, which can make the assistant hallucinate that the UI reset happened. Intercept /new in the web UI and chat API, call AgentLoop.reset_conversation, and clear the visible chat state.
<!-- SECTION:DESCRIPTION:END -->
