---
id: TASK-27
title: >-
  Backend: skill mini-app source artifact + source endpoint for
  @arrow-js/sandbox
status: In Progress
assignee:
  - '@me'
created_date: '2026-05-29 11:37'
updated_date: '2026-05-29 12:00'
labels:
  - skills
  - mini-app
  - sandbox
  - backend
dependencies: []
priority: high
ordinal: 27000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Define how a skill ships a sandboxed mini-app and serve it as a source map for @arrow-js/sandbox.

Spike (branch spike/arrow-sandbox) confirmed the model: sandbox({source},{output},hostBridge) runs the agent-authored code in a QuickJS+WASM VM, inline, with the host mediating all data via a hostBridge. The skill artifact changes from assets/index.html to a source object.

Changes:
- ui_app frontmatter declares a sandbox entry (e.g. app/main.ts, optional app/main.css) instead of an HTML asset entry.
- New GET /api/skills/{owner}/{name}/app-source returning {"main.ts": "...", "main.css": "..."} read from the skill dir (path-safe, scoped).
- Keep db/query + db/schema (now reached via the host bridge, not the mini-app directly).

Foundation for TASK-28 (frontend render).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 ui_app frontmatter can declare a sandbox source entry (main.ts/main.js + optional main.css)
- [x] #2 GET app-source returns the JSON source map for a skill's mini-app, path-safe and scoped
- [x] #3 Existing db/query + db/schema endpoints unchanged
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Added ui_app.kind ('iframe'|'sandbox') to SkillUiApp, inferred from entry extension (.ts/.js -> sandbox), with sandbox-entry normalization (basename must be main.ts/main.js; path kept, not assets-normalized). New GET /api/skills/{owner}/{name}/app-source returns {source:{main.ts|main.js, main.css?}, title} for sandbox skills (404 for iframe/missing). Tests: parser kind-inference (test_skill_loader.py), endpoint (test_skill_miniapp.py). Updated a test_skill_tools assertion (iframe apps now report kind). 709 pass; typecheck + lint clean. Docs deferred to TASK-29.
<!-- SECTION:NOTES:END -->
