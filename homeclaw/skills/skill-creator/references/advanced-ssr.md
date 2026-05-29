# Arrow framework + SSR (NOT for mini-apps)

> **Do not use any of this for homeclaw skill mini-apps.** Mini-apps are no-build
> CDN apps that import **only** `{ reactive, html }` from `@arrow-js/core` and
> mount with ``html`...`(el)``. Everything below requires a bundler/build step and
> a server runtime that homeclaw skill mini-apps do not have. It is kept here only
> so the mini-app references (`api.md`, `getting-started.md`, `examples.md`) stay
> focused. If you reach for `render`, `boundary`, `renderToString`, or `hydrate`
> in a mini-app, you are on the wrong path — go back to `getting-started.md`.

## Package split

- `@arrow-js/core`: `reactive`, `html`, `component`, `watch` — the only package mini-apps use.
- `@arrow-js/framework`: `render`, `boundary`, async component runtime.
- `@arrow-js/ssr`: `renderToString`, `serializePayload`.
- `@arrow-js/hydrate`: `hydrate`, `readPayload`.

## Framework + SSR API

- `render(root, view)` mounts a view to the DOM.
- `boundary(view, options)` gives async and hydration recovery boundaries.
- `renderToString(view)` returns `{ html, payload }`.
- `serializePayload(payload)` writes the SSR payload into the page.
- `hydrate(root, view, payload)` adopts matching SSR DOM in the browser.
