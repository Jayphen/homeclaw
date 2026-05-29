---
id: TASK-12
title: Extract a markdown_log helper for append-to-topic tools
status: To Do
assignee: []
created_date: '2026-05-29 05:02'
labels:
  - tier-3
  - duplication
  - agent
dependencies:
  - TASK-3
priority: low
ordinal: 12000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The 'create-with-header-or-append timestamped entry' markdown pattern is hand-rolled in contact_note (tools.py:288), bookmark_note (707), decision_log (2774), and note_save (407), each with its own '%Y-%m-%d %H:%M' literal. The 'scan lines for - [ prefix to index notes' logic is duplicated verbatim in bookmark_note_edit (737) and bookmark_note_delete (784). Extract a small markdown_log helper next to memory/markdown.py: append_entry(path, header, content, ts) and list_entry_line_indices(lines).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 markdown_log helper added and reused by the 4 append tools + 2 index sites
- [ ] #2 Single timestamp format; tests pass
<!-- AC:END -->
