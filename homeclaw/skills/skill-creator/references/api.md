# Arrow API Notes

Use this reference when you need the main runtime semantics quickly.

> **Provenance.** This file is a fork of the official `@arrow-js/skill` package
> (npm: `@arrow-js/skill`, repo: `github.com/standardagents/arrow-js`, MIT). The
> sections below are kept in sync with upstream `api.md` — pull genuine
> runtime-semantics fixes from there. The **Events** section below is a homeclaw
> addition (upstream omits it). SSR/framework material was moved to
> `advanced-ssr.md`: it does not apply to no-build mini-apps.

## `reactive()`

- Turns objects and arrays into live reactive state.
- Reads inside callable template expressions stay reactive.
- Plain values in template expressions render once.

## `html`

- Use the `html` tagged template literal to render DOM.
- `${data.foo}` is static.
- `${() => data.foo}` stays live.
- Return arrays of templates to render lists.
- Use `.key(...)` when DOM identity must survive reorders.

## `component()`

- Wraps a plain function and gives it stable instance semantics per render slot.
- Pass reactive objects as props.
- Read props lazily with callable expressions.
- Component props are live proxies, so `'foo' in props` and `Object.keys(props)` reflect the current source object.

## `watch()`

- Use for side effects, not primary rendering.
- Prefer template expressions for UI updates and `watch()` for imperative work.

## Events

- Bind listeners with an `@`-prefixed attribute, **not** the DOM `on*` attribute.
  `@click="${() => ...}"` works; `onclick="${...}"` silently does nothing.
- The value is a function: `@click="${() => state.count++}"`.
- Any DOM event works: `@input`, `@submit`, `@change`, `@keydown`, etc.
- Read the event with a parameter: `@input="${(e) => state.text = e.target.value}"`.
- Async handlers are fine: `@click="${async () => { await save() }}"`.

```html
<button @click="${() => state.count++}">Clicked ${() => state.count} times</button>
<input @input="${(e) => state.name = e.target.value}" />
```

## Not for mini-apps: framework + SSR

`render`, `boundary`, `renderToString`, `serializePayload`, and `hydrate` belong to
`@arrow-js/framework` / `@arrow-js/ssr` / `@arrow-js/hydrate` and require a build step.
They do **not** apply to no-build CDN mini-apps — see `advanced-ssr.md` if you are
genuinely scaffolding a full SSR app.
