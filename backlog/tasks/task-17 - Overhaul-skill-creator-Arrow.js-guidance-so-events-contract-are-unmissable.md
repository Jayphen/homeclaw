---
id: TASK-17
title: Overhaul skill-creator Arrow.js guidance so events/contract are unmissable
status: Done
assignee:
  - '@me'
created_date: '2026-05-29 05:32'
updated_date: '2026-05-29 05:52'
labels:
  - arrow-js
  - skills
  - docs
dependencies: []
references:
  - >-
    https://github.com/standardagents/arrow-js (packages/skill) — upstream
    @arrow-js/skill
priority: high
ordinal: 17000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Correct Arrow guidance exists but is off the default path while wrong patterns are on it. Fixes: (1) references/api.md documents reactive/html/component/watch/SSR but NOT event handling — add @click event binding (the thing most apps need). (2) SKILL.md's inline example (lines ~287-332) shows a list render with no events — add a minimal interactive @click example inline so a correct event example is in context without an extra read step. (3) read_skill lists references but does not return their contents, so the agent only sees examples.md if it deliberately opens it — auto-surface an Arrow cheat-sheet (via read_skill inlining or scaffold comments). (4) Add a hard 'mini-app contract' fence: ONLY import { reactive, html } from @arrow-js/core; mount with html`...`(el); events are @click; reactive is ${() => x}; do NOT use onclick, render(), boundary, renderToString, hydrate, or @arrow-js/framework. (5) Move the @arrow-js/framework + SSR/hydrate material (api.md:31-37, getting-started.md:50-55) out of the mini-app references or into a clearly separate advanced doc, since it does not apply to no-build mini-apps and invites the wrong rendering API.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 api.md documents @click event binding
- [x] #2 SKILL.md has a minimal correct interactive (@click) example inline
- [x] #3 A mini-app contract fence forbids onclick/render/framework imports and states the 4 core idioms
- [x] #4 SSR/framework material is separated from the mini-app references
- [x] #5 Correct examples are surfaced without requiring a deliberate skill_edit_file read
- [x] #6 Provenance note records that the Arrow references are a fork of @arrow-js/skill, with a pointer for syncing api.md fixes from upstream
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Upstream provenance: homeclaw's references/{api,examples,getting-started}.md are a fork of the official @arrow-js/skill package (npm: @arrow-js/skill, repo: github.com/standardagents/arrow-js, packages/skill — MIT, by the Arrow author). api.md is byte-identical to upstream; examples.md + getting-started.md were deliberately rewritten for homeclaw's no-build CDN mini-app case (we replaced upstream's Vite-scaffold/SSR/hydration/routing examples with @click handlers, db/query fetch, LAN vendoring, no-build mental model). Do NOT wire the npx installer or adopt the upstream skill wholesale: it executes external code, writes project-level agent files (.arrow-js/skill/, CLAUDE.md) that don't match homeclaw's runtime skill mechanism, and is altitude-mismatched (framework/SSR/routing heavy — the exact noise this task removes for mini-apps). Instead: (1) keep examples.md/getting-started.md as a homeclaw-specific fork; (2) add a provenance note + periodically diff upstream api.md and the shared top of examples.md for genuine runtime-semantics fixes worth pulling; (3) the 'api.md has no event section' gap is upstream too — consider a small upstream PR adding @click to their api.md so both stay in sync.

Implemented (docs/guidance only, no behavior change):
- references/api.md: added Events section (@click/@input, callable values, no on* attrs); removed Framework+SSR block; added upstream provenance + sync-from-upstream pointer.
- references/getting-started.md: removed SSR package-split block; noted mini-apps use only @arrow-js/core.
- references/advanced-ssr.md (NEW): houses moved framework/SSR/hydrate material, fenced 'NOT for mini-apps'.
- references/examples.md: provenance note (homeclaw-specific fork, do not re-sync wholesale).
- SKILL.md: added 'Mini-app contract' fence (5 idioms: import core only, mount html`...`(el), reactive state, ${() => x} live values, @click events) + forbidden list (onclick/render/boundary/renderToString/hydrate/@arrow-js/framework) + minimal interactive @click example inline. Refreshed reference list (api.md now lists events; advanced-ssr.md marked not-for-mini-apps).
- agent/tools.py _default_ui_app_html scaffold: added contract comment block at top of <script>.
- agent/loop.py system prompt: terse Arrow contract clause (@click not onclick; wrap changing values in () =>) at the point Arrow is first introduced — surfaces the gotchas before any reference read.
AC#5 satisfied by putting the contract+example in SKILL.md (always returned by read_skill 'instructions'; references only return filenames) plus scaffold comment + system-prompt clause.
Verified: typecheck 0 errors, ruff clean, 648 tests pass.
<!-- SECTION:NOTES:END -->
