---
id: TASK-18
title: Add write-time Arrow.js lint to skill UI-app writes
status: Done
assignee:
  - '@me'
created_date: '2026-05-29 05:32'
updated_date: '2026-05-29 06:15'
labels:
  - arrow-js
  - skills
  - dx
dependencies: []
priority: medium
ordinal: 18000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Subtly-wrong Arrow apps fail silently (blank/stale UI, no surfaced console error), and the only feedback loop is the optional browser_enabled web_browse check — so the agent has no signal it is close and reverts to plain HTML/CSS. When skill_enable_ui_app or skill_edit_file writes an assets/*.html, run a lightweight lint that returns warnings the agent must address for the known footguns: (a) on*="${...}" event attributes (onclick/oninput/onchange) instead of @event; (b) likely-non-reactive ${state.x} (bare member access without an arrow) inside an html` template; (c) imports of @arrow-js/framework or use of render(/boundary(/renderToString( in a no-build mini-app; (d) missing html`...`(mountEl) mount call. Warnings only (do not block writes), surfaced in the tool result so the agent self-corrects.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 skill_enable_ui_app and skill_edit_file run the lint on assets/*.html writes
- [x] #2 Lint flags on*-attribute handlers, non-reactive interpolations, framework imports, and missing mount
- [x] #3 Findings are returned as warnings in the tool result (non-blocking); unit tests cover each rule
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented a non-blocking write-time Arrow lint.

New module homeclaw/plugins/skills/arrow_lint.py: lint_arrow_html(source) -> list[str]. A single-pass, template-literal-aware lexer produces (cleaned, html_interps, mounted, has_html), then four rules run:
  (a) on*="${...}" attrs -> use @event (regex on comment-stripped source; (?<![\w-]) guards data-*)
  (b) bare dotted member-access interpolations sitting directly in html` template text (any nesting depth) -> wrap in () =>. Excludes calls/arrows/operators/literals; ignores interpolations in plain (non-html) template strings.
  (c) @arrow-js/framework|ssr|hydrate imports + render(/boundary(/renderToString(/serializePayload(/hydrate( calls
  (d) missing mount: has html` but no html`...`(node) immediate-invoke and no (document.* call (so deferred var(document.body) mounts pass)
Comments are neutralized first (HTML comments stripped; JS // and /* */ skipped by the lexer in code context AFTER strings/URLs are consumed) so our own scaffolds/reference app — which mention these footguns in prose — don't self-trip.

Wiring (homeclaw/agent/tools.py): module-level _arrow_lint_warnings(file_rel, content) lints only assets/*.html. Called from skill_edit_file (write + find/replace modes) and skill_enable_ui_app; findings attached as result['arrow_warnings'] (only when non-empty). Non-blocking — the write always succeeds.

Guidance: skill-creator SKILL.md Notes now tells the agent arrow_warnings will appear and to treat them as must-fix.

Tests: tests/unit/test_arrow_lint.py (22) covers each rule + false-negative guards (data-*, method.render(), plain template strings, deferred mount), comment false-positives, plain HTML, empty, multi-issue, and a golden test that the shipped reference-mini-app.html lints clean (ties TASK-16<->18). tests/unit/test_tools/test_skill_tools.py (+6) covers skill_edit_file write/find-replace, non-assets skip, good-html no-warnings, and skill_enable_ui_app bad-html + default-scaffold-clean.

Verified: typecheck 0 errors, ruff clean, 676 tests pass.
<!-- SECTION:NOTES:END -->
