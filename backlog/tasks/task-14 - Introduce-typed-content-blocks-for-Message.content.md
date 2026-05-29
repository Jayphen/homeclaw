---
id: TASK-14
title: Introduce typed content blocks for Message.content
status: To Do
assignee: []
created_date: '2026-05-29 05:02'
labels:
  - tier-4
  - typing
  - agent-loop
dependencies: []
priority: low
ordinal: 14000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Message.content is str | list[Any], so the {'type':'text'|'image',...} block shape is reconstructed by hand and guarded with isinstance(block, dict)/block.get('type') in ~6 places (loop.py:298,466,776,820,944,1345; additional_context.py). Define TextBlock/ImageBlock Pydantic models (or a ContentBlock union) and type content as str | list[ContentBlock]. Deletes every dict guard and .get() and makes the multimodal contract explicit.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 ContentBlock union (TextBlock/ImageBlock) defined; Message.content typed with it
- [ ] #2 isinstance(block, dict)/.get('type') ritual removed at call sites; tests + typecheck pass
<!-- AC:END -->
