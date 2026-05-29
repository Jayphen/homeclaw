---
id: TASK-9
title: Introduce BaseChannel + OutboundChannel Protocol for channel adapters
status: To Do
assignee: []
created_date: '2026-05-29 05:01'
labels:
  - tier-3
  - duplication
  - channels
dependencies: []
priority: medium
ordinal: 9000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
TelegramChannel and WhatsAppChannel re-implement _run_and_reply, _reverse_user_map, _has_person, _send_to_person, _send_image_to_person, _split_message and dispatcher registration with bodies differing only by transport (~90-130 lines deletable). There is no Channel base/Protocol, violating CLAUDE.md's 'interfaces use typing.Protocol' rule — the dispatcher takes six loose callables. Add homeclaw/channel/base.py (BaseChannel, template-method on _reply/_format/_send_raw), a @runtime_checkable OutboundChannel Protocol, and a _resolve_routing() helper to kill the 'telegram_dm'/'telegram_group' string-literal branching duplicated across 4 sites (consider a SourceChannel StrEnum).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 BaseChannel owns the shared methods; adapters keep only transport-specific overrides
- [ ] #2 OutboundChannel Protocol defined and used by the dispatcher instead of six callables
- [ ] #3 _resolve_routing centralizes group/DM + source_channel resolution; tests pass
<!-- AC:END -->
