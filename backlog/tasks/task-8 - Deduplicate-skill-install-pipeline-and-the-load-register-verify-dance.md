---
id: TASK-8
title: Deduplicate skill install pipeline and the load/register/verify dance
status: To Do
assignee: []
created_date: '2026-05-29 05:01'
labels:
  - tier-3
  - duplication
  - plugins
dependencies: []
priority: medium
ordinal: 8000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
routes/skills.py:221-372 and tools.py:2070-2271 are a near line-for-line copy of the same install-from-URL pipeline and have already drifted (one runs verify_skill, one does not). Separately, the 'load_skill -> register -> set loaded/warning -> catch Exception' block is copy-pasted 6x in tools.py (1694,1830,1908,2012,2139) with message drift. Extract a canonical homeclaw/plugins/skills/install.py::install_skill_from_url(...) and a _hot_reload_skill(...) helper; route + tool become thin adapters. ~200 lines deletable; one definition of load-failure behavior. NOTE: the /install route is AdminDep-gated, so the missing approval-staging there is by design, not a security hole — this is a duplication/drift fix.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Single canonical installer used by both the API route and the agent tool
- [ ] #2 Single _hot_reload_skill helper replaces the 6 copies; load-failure behavior consistent
- [ ] #3 Verification behavior is consistent across both entry points; tests pass
<!-- AC:END -->
