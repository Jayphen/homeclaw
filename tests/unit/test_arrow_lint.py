"""Tests for the Arrow.js mini-app write-time lint (homeclaw.plugins.skills.arrow_lint)."""

from __future__ import annotations

from pathlib import Path

from homeclaw.plugins.skills.arrow_lint import lint_arrow_html

_CDN = "https://cdn.jsdelivr.net/npm/@arrow-js/core/dist/index.mjs"
CORE_IMPORT = f"import {{ reactive, html }} from '{_CDN}'"


def _app(body: str) -> str:
    head = f"<script type='module'>\n{CORE_IMPORT}\nconst state = reactive({{count: 0}})\n"
    return f"{head}{body}\n</script>"


def _joined(warnings: list[str]) -> str:
    return "\n".join(warnings).lower()


# ---------------------------------------------------------------------------
# (a) on*="${...}" event attributes
# ---------------------------------------------------------------------------


def test_flags_onclick_attribute() -> None:
    src = _app('html`<button onclick="${() => state.count++}">x</button>`(document.body)')
    warnings = lint_arrow_html(src)
    assert any("onclick" in w and "@click" in w for w in warnings)


def test_flags_oninput_attribute() -> None:
    src = _app('html`<input oninput="${(e) => state.t = e.target.value}" />`(document.body)')
    assert any("oninput" in w and "@input" in w for w in lint_arrow_html(src))


def test_does_not_flag_at_click() -> None:
    src = _app('html`<button @click="${() => state.count++}">x</button>`(document.body)')
    assert not any("@click" in w and "will not fire" in w for w in lint_arrow_html(src))


def test_does_not_flag_data_attribute_lookalike() -> None:
    # data-onfoo must not be mistaken for an on* handler
    src = _app('html`<div data-online="${() => state.count}"></div>`(document.body)')
    assert not any("will not fire" in w for w in lint_arrow_html(src))


# ---------------------------------------------------------------------------
# (b) non-reactive bare member-access interpolations
# ---------------------------------------------------------------------------


def test_flags_bare_member_interpolation() -> None:
    src = _app("html`<p>${state.count}</p>`(document.body)")
    assert any("render only once" in w and "state.count" in w for w in lint_arrow_html(src))


def test_does_not_flag_arrow_wrapped_interpolation() -> None:
    src = _app("html`<p>${() => state.count}</p>`(document.body)")
    assert not any("render only once" in w for w in lint_arrow_html(src))


def test_does_not_flag_static_literal_interpolation() -> None:
    src = _app("html`<h1>${'Items'}</h1>`(document.body)")
    assert not any("render only once" in w for w in lint_arrow_html(src))


def test_flags_bare_interpolation_nested_in_map() -> None:
    src = _app(
        "html`<ul>${() => state.items.map(i => html`<li>${i.name}</li>`)}</ul>`(document.body)"
    )
    warnings = lint_arrow_html(src)
    assert any("render only once" in w and "i.name" in w for w in warnings)


def test_does_not_flag_member_access_in_plain_template_string() -> None:
    # `Bearer ${token}` style strings (not html templates) must be ignored
    src = _app(
        "const headers = {Authorization: `Bearer ${state.count}`}\n"
        "html`<p>${() => state.count}</p>`(document.body)"
    )
    assert not any("render only once" in w for w in lint_arrow_html(src))


# ---------------------------------------------------------------------------
# (c) framework / SSR imports and calls
# ---------------------------------------------------------------------------


def test_flags_framework_import() -> None:
    src = "import { render } from '@arrow-js/framework'\nconst v = html`<p>x</p>`(document.body)"
    assert any("@arrow-js/framework" in w for w in lint_arrow_html(src))


def test_flags_ssr_import() -> None:
    src = "import { renderToString } from '@arrow-js/ssr'\nhtml`<p>x</p>`(document.body)"
    assert any("@arrow-js/ssr" in w for w in lint_arrow_html(src))


def test_flags_render_call() -> None:
    src = _app("const v = html`<p>x</p>`\nrender(document.body, v)")
    assert any(w.startswith("`render(") for w in lint_arrow_html(src))


def test_does_not_flag_method_named_render() -> None:
    # obj.render( is a method on something else, not the framework free function
    src = _app("widget.render()\nhtml`<p>${() => state.count}</p>`(document.body)")
    assert not any("framework/SSR runtime" in w for w in lint_arrow_html(src))


def test_does_not_flag_core_import() -> None:
    src = _app("html`<p>${() => state.count}</p>`(document.body)")
    assert not any("@arrow-js/core" in w for w in lint_arrow_html(src))


# ---------------------------------------------------------------------------
# (d) missing mount
# ---------------------------------------------------------------------------


def test_flags_missing_mount() -> None:
    src = _app("html`<p>${() => state.count}</p>`")  # never called with a node
    assert any("no mount call" in w.lower() for w in lint_arrow_html(src))


def test_does_not_flag_immediate_mount() -> None:
    src = _app("html`<p>${() => state.count}</p>`(document.body)")
    assert not any("no mount call" in w.lower() for w in lint_arrow_html(src))


def test_does_not_flag_deferred_variable_mount() -> None:
    src = _app("const view = html`<p>${() => state.count}</p>`\nview(document.body)")
    assert not any("no mount call" in w.lower() for w in lint_arrow_html(src))


# ---------------------------------------------------------------------------
# (e) HTML comments inside an html`` template — a mount-time fatal
#     (browser-verified: any <!-- --> inside the template throws "Invalid HTML
#      position" and the whole app renders blank)
# ---------------------------------------------------------------------------


def test_flags_html_comment_inside_template() -> None:
    src = _app("html`<!-- a note -->\n<p>${() => state.count}</p>`(document.body)")
    warnings = lint_arrow_html(src)
    assert any("comment" in w.lower() and "invalid html position" in w.lower() for w in warnings)


def test_flags_html_comment_between_elements_in_template() -> None:
    src = _app(
        "html`<div>${() => state.count}</div><!-- x -->"
        "<div>${() => state.count}</div>`(document.body)"
    )
    assert any("comment" in w.lower() for w in lint_arrow_html(src))


# ---------------------------------------------------------------------------
# (f) partial attribute interpolation — a mount-time fatal
# ---------------------------------------------------------------------------


def test_flags_partial_attribute_interpolation() -> None:
    src = _app('html`<span class="card ${() => state.count}">x</span>`(document.body)')
    warnings = lint_arrow_html(src)
    assert any("attribute" in w.lower() and "invalid html position" in w.lower() for w in warnings)


def test_flags_trailing_partial_attribute_interpolation() -> None:
    src = _app('html`<span class="${() => state.count} card">x</span>`(document.body)')
    assert any("attribute" in w.lower() for w in lint_arrow_html(src))


def test_does_not_flag_whole_value_attribute_interpolation() -> None:
    src = _app("html`<span class=\"${() => state.count ? 'a' : 'b'}\">x</span>`(document.body)")
    assert not any("attribute mixes static text" in w.lower() for w in lint_arrow_html(src))


def test_does_not_flag_static_only_attribute() -> None:
    src = _app('html`<span class="card big">${() => state.count}</span>`(document.body)')
    assert not any("attribute mixes static text" in w.lower() for w in lint_arrow_html(src))


# ---------------------------------------------------------------------------
# Comments, non-arrow input, and the shipped reference app
# ---------------------------------------------------------------------------


def test_js_comments_do_not_cause_false_positives() -> None:
    # JS // and /* */ comments that mention footgun keywords must not trip rules.
    src = _app(
        '// never use onclick="..." or @arrow-js/framework; don\'t call render()\n'
        "/* renderToString() is SSR-only */\n"
        "html`<p>${() => state.count}</p>`(document.body)"
    )
    assert lint_arrow_html(src) == []


def test_page_comments_outside_template_are_ignored() -> None:
    # An HTML comment in page markup (not inside a template) — even one that
    # mentions onclick or a backticked html`...` — must not be linted.
    src = (
        "<head><!-- copy this: html`...`(document.body); avoid onclick --></head>\n"
        f"<script type='module'>\n{CORE_IMPORT}\nconst state = reactive({{count: 0}})\n"
        "html`<p>${() => state.count}</p>`(document.body)\n</script>"
    )
    assert lint_arrow_html(src) == []


def test_plain_html_is_not_linted() -> None:
    src = '<html><body><button onclick="doThing()">Go</button></body></html>'
    assert lint_arrow_html(src) == []


def test_empty_source() -> None:
    assert lint_arrow_html("") == []


def test_shipped_reference_app_follows_sandbox_contract() -> None:
    """The canonical reference mini-app is now sandbox source (TASK-29).

    arrow_lint targets the legacy single-HTML model (its missing-mount rule would
    even false-positive on a sandbox `export default`), so instead of linting we
    assert the source-payload contract the reference must teach.
    """
    ref = Path("homeclaw/skills/skill-creator/assets/reference-mini-app.ts")
    assert ref.is_file(), f"reference app missing at {ref}"
    src = ref.read_text()
    assert "from '@arrow-js/core'" in src
    assert "from 'homeclaw'" in src  # host bridge, not fetch
    assert "export default" in src
    assert "fetch('" not in src  # no real network call (comments may mention fetch)
    assert "localStorage" not in src  # the VM has no token


def test_reports_multiple_distinct_issues_together() -> None:
    src = _app('html`<button onclick="${() => state.count++}">${state.count}</button>`')
    warnings = _joined(lint_arrow_html(src))
    assert "onclick" in warnings  # (a)
    assert "render only once" in warnings  # (b)
    assert "no mount call" in warnings  # (d)
