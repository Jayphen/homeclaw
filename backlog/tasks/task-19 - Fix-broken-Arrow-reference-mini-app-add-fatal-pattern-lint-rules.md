---
id: TASK-19
title: Fix broken Arrow reference mini-app + add fatal-pattern lint rules
status: Done
assignee:
  - '@me'
created_date: '2026-05-29 07:10'
updated_date: '2026-05-29 07:32'
labels: []
dependencies: []
ordinal: 19000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
ROOT CAUSE: reference-mini-app.html throws 'Invalid HTML position' at mount (HTML comments inside the html`` template). Agents copy it and fail. Browser-bisected two fatal, statically-detectable patterns: (1) HTML comments inside an html`` template, (2) partial attribute interpolation (static text + ${} in one attribute). Rewrite the reference app + default scaffold comment-free; add both lint rules to arrow_lint.py (the lint pre-stripped comments so it never caught rule 1).
<!-- SECTION:DESCRIPTION:END -->
