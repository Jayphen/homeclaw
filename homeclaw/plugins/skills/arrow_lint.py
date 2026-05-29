"""Lightweight, non-blocking lint for Arrow.js skill mini-apps.

Subtly-wrong Arrow apps fail silently — a blank or stale UI with no surfaced
console error — so the agent gets no signal it is close and reverts to plain
HTML/CSS. This module flags the handful of known footguns at write time so the
agent can self-correct. It returns *warnings only* and never blocks a write.

The four rules mirror the mini-app contract in the skill-creator skill:

  (a) ``on*="${...}"`` event attributes (e.g. ``onclick``) instead of ``@event``
  (b) likely-non-reactive ``${state.x}`` (a bare member access with no arrow)
      sitting directly in an ``html`...``` template
  (c) imports of ``@arrow-js/framework`` / ``/ssr`` / ``/hydrate`` or calls to
      the framework/SSR runtime (``render``, ``boundary``, ``renderToString``, …)
      in a no-build mini-app
  (d) a missing ``html`...`(mountEl)`` mount call

The checks run on a comment-stripped view of the source so the explanatory
comments in our own scaffolds and reference app (which deliberately mention
``onclick``, ``@arrow-js/framework``, etc.) do not trip the lint.
"""

from __future__ import annotations

import re

_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)

# onclick="${...}" / oninput='${...}' — an Arrow interpolation bound to a DOM
# on* attribute. The (?<![\w-]) guard avoids matching data-onfoo / custom attrs.
_ON_ATTR_RE = re.compile(r"""(?<![\w-])on([a-z]+)\s*=\s*["']\s*\$\{""")

# import/require of a non-core Arrow package (these need a bundler).
_FRAMEWORK_IMPORT_RE = re.compile(
    r"""(?:from|import)\s*\(?\s*['"][^'"]*@arrow-js/(framework|ssr|hydrate)\b"""
)

# Calls into the framework/SSR runtime. (?<![\w.]) avoids foo.render(/prerender(.
_FRAMEWORK_CALL_RE = re.compile(
    r"""(?<![\w.])(render|boundary|renderToString|serializePayload|hydrate)\s*\("""
)

# A bare dotted member access and nothing else: state.count, item.name, a.b.c.
# Excludes calls (has "("), arrows (has "=>"), operators, and literals.
_MEMBER_ACCESS_RE = re.compile(r"^[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)+$")

# A mount that does not immediately follow a template: view(document.body).
_DOC_MOUNT_RE = re.compile(r"\(\s*document\.\w+")


def _scan(src: str) -> tuple[str, list[str], bool, bool]:
    """Single-pass, template-literal-aware lexer.

    Returns ``(cleaned, html_interps, html_mounted, has_html)``:

      cleaned       src with JS comments removed (string/template contents,
                    including CDN URLs, are preserved so import detection works)
      html_interps  the expression text of every ``${...}`` sitting directly in
                    the text of an ``html`...``` template, at any nesting depth
      html_mounted  some ``html`...``` is immediately invoked: ``html`...`(node)``
      has_html      at least one ``html`...``` template exists
    """
    n = len(src)
    i = 0
    out: list[str] = []
    # Stack frames:
    #   ["text", is_html]                      -> inside template text
    #   ["expr", brace_depth, start, in_html]  -> inside a ${...} interpolation
    stack: list[list] = []
    html_interps: list[str] = []
    html_mounted = False
    has_html = False

    while i < n:
        frame = stack[-1] if stack else None

        # --- template text context -------------------------------------------
        if frame is not None and frame[0] == "text":
            is_html = frame[1]
            c = src[i]
            if c == "\\":
                out.append(src[i : i + 2])
                i += 2
                continue
            if c == "`":
                out.append(c)
                stack.pop()
                i += 1
                if is_html:
                    j = i
                    while j < n and src[j] in " \t\r\n":
                        j += 1
                    if j < n and src[j] == "(":
                        html_mounted = True
                continue
            if c == "$" and i + 1 < n and src[i + 1] == "{":
                out.append("${")
                stack.append(["expr", 0, i + 2, is_html])
                i += 2
                continue
            out.append(c)
            i += 1
            continue

        # --- code context (top level or inside a ${...} expression) ----------
        c = src[i]

        # JS comments — safe to strip here: string/URL contents are consumed by
        # the quote handler below and never reach this branch.
        if c == "/" and i + 1 < n and src[i + 1] == "/":
            out.append(" ")
            i += 2
            while i < n and src[i] != "\n":
                i += 1
            continue
        if c == "/" and i + 1 < n and src[i + 1] == "*":
            out.append(" ")
            i += 2
            while i + 1 < n and not (src[i] == "*" and src[i + 1] == "/"):
                i += 1
            i += 2
            continue

        # String literals — copy through verbatim (preserves import URLs).
        if c in "'\"":
            quote = c
            out.append(c)
            i += 1
            while i < n:
                if src[i] == "\\":
                    out.append(src[i : i + 2])
                    i += 2
                    continue
                out.append(src[i])
                if src[i] == quote:
                    i += 1
                    break
                i += 1
            continue

        # Opening a template literal — tagged with `html`?
        if c == "`":
            j = i - 1
            while j >= 0 and src[j] in " \t\r\n":
                j -= 1
            end = j
            while j >= 0 and (src[j].isalnum() or src[j] in "_$"):
                j -= 1
            is_html = src[j + 1 : end + 1] == "html"
            if is_html:
                has_html = True
            out.append(c)
            stack.append(["text", is_html])
            i += 1
            continue

        # Brace tracking inside an interpolation expression.
        if frame is not None and frame[0] == "expr":
            if c == "{":
                frame[1] += 1
                out.append(c)
                i += 1
                continue
            if c == "}":
                if frame[1] == 0:
                    expr_text = src[frame[2] : i]
                    in_html = frame[3]
                    stack.pop()
                    out.append(c)
                    i += 1
                    if in_html:
                        html_interps.append(expr_text)
                    continue
                frame[1] -= 1
                out.append(c)
                i += 1
                continue

        out.append(c)
        i += 1

    return "".join(out), html_interps, html_mounted, has_html


def lint_arrow_html(source: str) -> list[str]:
    """Return non-blocking warnings for known Arrow.js mini-app footguns.

    An empty list means no issues were found (or the file is not an Arrow app).
    """
    if not source or ("@arrow-js" not in source and "html`" not in source):
        # Not an Arrow mini-app (plain HTML/CSS, or some other page) — skip.
        return []

    src = _HTML_COMMENT_RE.sub(" ", source)
    cleaned, interps, mounted, has_html = _scan(src)
    warnings: list[str] = []

    # (a) on*="${...}" event attributes
    seen_events: set[str] = set()
    for m in _ON_ATTR_RE.finditer(cleaned):
        event = m.group(1)
        if event in seen_events:
            continue
        seen_events.add(event)
        warnings.append(
            f'`on{event}="${{...}}"` will not fire — Arrow ignores DOM `on*` '
            f"attributes, so the handler runs once at render and never on the event. "
            f'Use `@{event}="${{() => ...}}"` instead.'
        )

    # (c) framework / SSR imports and calls (mini-apps use only @arrow-js/core)
    for pkg in sorted({m.group(1) for m in _FRAMEWORK_IMPORT_RE.finditer(cleaned)}):
        warnings.append(
            f"Importing from `@arrow-js/{pkg}` — a no-build mini-app uses only "
            f"`@arrow-js/core` (`reactive`, `html`). `@arrow-js/{pkg}` needs a bundler "
            f"and will not load from a CDN."
        )
    for fn in sorted({m.group(1) for m in _FRAMEWORK_CALL_RE.finditer(cleaned)}):
        warnings.append(
            f"`{fn}(...)` is part of the Arrow framework/SSR runtime, not the mini-app "
            f"core. Mount by calling the template with a DOM node "
            f"(`html`...`(document.body)`), not `{fn}()`."
        )

    # (d) missing mount
    if has_html and not (mounted or _DOC_MOUNT_RE.search(cleaned)):
        warnings.append(
            "No mount call found — an `html`...`` template only renders when you call "
            "it with a DOM node, e.g. `html`...`(document.body)`. Without it the UI "
            "stays blank."
        )

    # (b) bare member-access interpolations inside html templates (non-reactive)
    bare: list[str] = []
    seen_exprs: set[str] = set()
    for expr in interps:
        e = expr.strip()
        if e and e not in seen_exprs and _MEMBER_ACCESS_RE.match(e):
            seen_exprs.add(e)
            bare.append(e)
    if bare:
        shown = ", ".join(f"`${{{e}}}`" for e in bare[:5])
        more = "" if len(bare) <= 5 else f" (+{len(bare) - 5} more)"
        warnings.append(
            f"These read state directly and render only once: {shown}{more}. If the "
            f"value changes, wrap it in an arrow so it stays reactive — "
            f"`${{() => {bare[0]}}}`."
        )

    return warnings
