---
id: TASK-29
title: >-
  Authoring: rewrite skill-creator for sandbox payloads + reference app; retire
  HTML-era lint/boundary
status: Done
assignee:
  - '@me'
created_date: '2026-05-29 11:37'
updated_date: '2026-05-29 15:36'
labels:
  - skills
  - mini-app
  - sandbox
  - docs
dependencies:
  - TASK-28
priority: medium
ordinal: 29000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Move skill mini-app authoring from single-HTML to sandbox source payloads.

Changes:
- Rewrite skill-creator SKILL.md mini-app guidance to produce a source object (main.ts/main.css). Adopt Arrow's official create_arrow_sandbox tool schema + agent prompt (https://arrow-js.com) as the authoring contract.
- Ship a working reference sandbox mini-app (source-based) that uses the host db bridge.
- Retire/replace arrow_lint.py fatal-pattern rules and the auto-injected JS error boundary: the sandbox precompiles templates (errors surface via onError) so the blank-page failure mode and the HTML-comment/partial-attr footguns no longer apply the same way. Keep whatever still adds value.
- Update docs/ pages for the new mini-app model.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 skill-creator SKILL.md teaches the sandbox source-payload model (Arrow's tool schema + prompt)
- [x] #2 A working source-based reference mini-app ships and uses the host db bridge
- [x] #3 arrow_lint + injected error boundary reviewed: retired or re-scoped for the sandbox model; docs updated
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
skill_enable_ui_app now writes a sandbox app: app/main.ts (+ app/main.css) + ui-app:{entry: app/main.ts, kind: sandbox}, with a working default scaffold using the 'homeclaw' bridge (no fetch/token). New params main_ts/main_css (dropped html_content/entry). Reference app replaced: assets/reference-mini-app.html -> reference-mini-app.ts (+ .css), host-bridge query, keyed list, loading/error/empty. SKILL.md mini-app section + references/getting-started.md + examples.md rewritten for the source-payload + bridge model (bare @arrow-js/core import, export default, no CDN/mount/token). loop.py system-prompt guidance updated. arrow_lint REVIEWED: kept for legacy iframe (assets/*.html) only — it no-ops on sandbox source and its missing-mount rule would false-positive on export default; removed from the sandbox tool path. Error-boundary removal deferred to TASK-30 (it's part of retiring the iframe asset path). Docs site page updated. 707 tests pass, typecheck + lint clean, ui build OK.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Shipped in PR #168. skill_enable_ui_app writes sandbox apps (app/main.ts + main.css via the homeclaw bridge); source-based reference app; SKILL.md/references/system-prompt/docs rewritten for the sandbox contract; arrow_lint kept for legacy iframe only. 707 tests pass.
<!-- SECTION:FINAL_SUMMARY:END -->
