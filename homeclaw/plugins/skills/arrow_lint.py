"""Lightweight, non-blocking lint for Arrow.js skill mini-apps.

Subtly-wrong Arrow apps fail silently — a blank or stale UI with no surfaced
console error — so the agent gets no signal it is close and reverts to plain
HTML/CSS. This module flags the handful of known footguns at write time so the
agent can self-correct. It returns *warnings only* and never blocks a write.

The rules mirror the mini-app contract in the skill-creator skill:

  (a) ``on*="${...}"`` event attributes (e.g. ``onclick``) instead of ``@event``
  (b) likely-non-reactive ``${state.x}`` (a bare member access with no arrow)
      sitting directly in an ``html`...``` template
  (c) imports of ``@arrow-js/framework`` / ``/ssr`` / ``/hydrate`` or calls to
      the framework/SSR runtime (``render``, ``boundary``, ``renderToString``, …)
      in a no-build mini-app
  (d) a missing ``html`...`(mountEl)`` mount call
  (e) an HTML comment (``<!-- ... -->``) *inside* an ``html`...``` template —
      Arrow throws ``Invalid HTML position`` at mount and the app renders blank
  (f) a "partial" attribute value that mixes static text with a ``${...}``
      interpolation (``class="foo ${...}"``) — also a fatal ``Invalid HTML
      position`` at mount; the interpolation must be the whole attribute value

Rules (e) and (f) are mount-time fatals, browser-verified by bisecting a real
failing app. They are the reason "the agent can't one-shot a working UI": the
shipped reference app itself once carried rule (e), and the whole template-aware
scan below is needed because comment contents must be inspected *in context*
(an ``onclick`` mentioned in a ``<head>`` comment must not trip rule (a), but a
comment inside the template body must trip rule (e)).
"""

from __future__ import annotations

import re

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


class _Scan:
    """Result of the template-literal-aware lexer pass."""

    __slots__ = (
        "cleaned",
        "html_interps",
        "html_mounted",
        "has_html",
        "html_comments",
        "partial_attrs",
    )

    def __init__(self) -> None:
        self.cleaned: str = ""
        self.html_interps: list[str] = []
        self.html_mounted: bool = False
        self.has_html: bool = False
        # Count of ``<!-- ... -->`` comments found *inside* html templates.
        self.html_comments: int = 0
        # Count of attribute values that mix static text with a ``${...}``.
        self.partial_attrs: int = 0


def _scan(src: str) -> _Scan:
    """Single-pass, template-literal-aware lexer over the *raw* source.

    Returns a :class:`_Scan`. ``cleaned`` is the source with JS comments and
    *all* HTML comments removed (string/template contents — including CDN URLs —
    are preserved so import detection works), so the regex rules never match
    comment or string text. The remaining fields capture context the regexes
    cannot see:

      html_interps   the expression text of every ``${...}`` sitting directly in
                     the text of an ``html`...``` template, at any nesting depth
      html_mounted   some ``html`...``` is immediately invoked: ``html`...`(node)``
      has_html       at least one ``html`...``` template exists
      html_comments  HTML comments found inside html-template text (fatal)
      partial_attrs  attribute values mixing static text with ``${...}`` (fatal)

    The scan runs on raw source (not a comment-pre-stripped copy) because rule
    (e) must know whether a comment sits *inside* a template; HTML comments in
    plain page markup (e.g. ``<head>``) are stripped here but not counted.
    """
    n = len(src)
    i = 0
    out: list[str] = []
    res = _Scan()
    # Stack frames:
    #   ["text", is_html, in_tag, attr_quote, attr_static, attr_interp]
    #       -> inside template text. The last four track attribute context so
    #          rule (f) can fire when a value has both static text and a ${...}.
    #   ["expr", brace_depth, start, in_html]  -> inside a ${...} interpolation
    stack: list[list] = []

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
            # HTML comment inside template text — strip it, and (for html
            # templates) count it as a fatal mount-time footgun.
            if c == "<" and src.startswith("<!--", i):
                end = src.find("-->", i + 4)
                end = end + 3 if end != -1 else n
                if is_html:
                    res.html_comments += 1
                out.append(" ")
                i = end
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
                        res.html_mounted = True
                continue
            if c == "$" and i + 1 < n and src[i + 1] == "{":
                out.append("${")
                if is_html and frame[3] is not None:
                    frame[5] = True  # interpolation appears in an attribute value
                stack.append(["expr", 0, i + 2, is_html])
                i += 2
                continue
            # Track attribute context (html templates only) for rule (f).
            if is_html:
                if frame[3] is not None:
                    if c == frame[3]:  # closing quote of the attribute value
                        if frame[4] and frame[5]:
                            res.partial_attrs += 1
                        frame[3] = None
                        frame[4] = False
                        frame[5] = False
                    elif not c.isspace():
                        frame[4] = True  # static, non-space text in the value
                elif c == "<":
                    frame[2] = True  # entering a tag
                elif c == ">":
                    frame[2] = False  # leaving a tag
                elif frame[2] and c in "\"'":
                    frame[3] = c  # opening an attribute value
                    frame[4] = False
                    frame[5] = False
            out.append(c)
            i += 1
            continue

        # --- code context (top level or inside a ${...} expression) ----------
        c = src[i]

        # HTML comments in page markup / between code — strip (don't count). This
        # also guards the backtick handler below from opening a spurious template
        # on a `html`...`` mention inside a <head> explanatory comment.
        if c == "<" and src.startswith("<!--", i):
            end = src.find("-->", i + 4)
            i = end + 3 if end != -1 else n
            out.append(" ")
            continue

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
                res.has_html = True
            out.append(c)
            stack.append(["text", is_html, False, None, False, False])
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
                        res.html_interps.append(expr_text)
                    continue
                frame[1] -= 1
                out.append(c)
                i += 1
                continue

        out.append(c)
        i += 1

    res.cleaned = "".join(out)
    return res


def lint_arrow_html(source: str) -> list[str]:
    """Return non-blocking warnings for known Arrow.js mini-app footguns.

    An empty list means no issues were found (or the file is not an Arrow app).
    """
    if not source or ("@arrow-js" not in source and "html`" not in source):
        # Not an Arrow mini-app (plain HTML/CSS, or some other page) — skip.
        return []

    scan = _scan(source)
    cleaned = scan.cleaned
    warnings: list[str] = []

    # (e) HTML comments inside an html`` template — a mount-time fatal. Listed
    # first because it blanks the entire app and is the most common cause of a
    # silently-broken mini-app.
    if scan.html_comments:
        warnings.append(
            "HTML comments (`<!-- ... -->`) inside an `html`...`` template throw "
            "`Invalid HTML position` at mount and the whole app renders blank. Move "
            "every comment out of the template (use JS `//` comments above it) or "
            "delete it."
        )

    # (f) partial attribute interpolation — also a mount-time fatal.
    if scan.partial_attrs:
        warnings.append(
            "An attribute mixes static text with a `${...}` interpolation (e.g. "
            '`class="card ${() => ...}"`). Arrow throws `Invalid HTML position` for '
            "this — the interpolation must be the ENTIRE attribute value. Build the "
            'whole string inside one arrow: `class="${() => `card ${extra}`}"`.'
        )

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
    if scan.has_html and not (scan.html_mounted or _DOC_MOUNT_RE.search(cleaned)):
        warnings.append(
            "No mount call found — an `html`...`` template only renders when you call "
            "it with a DOM node, e.g. `html`...`(document.body)`. Without it the UI "
            "stays blank."
        )

    # (b) bare member-access interpolations inside html templates (non-reactive)
    bare: list[str] = []
    seen_exprs: set[str] = set()
    for expr in scan.html_interps:
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
