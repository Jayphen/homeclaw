# Arrow Getting Started (homeclaw mini-apps)

homeclaw mini-apps run inside a sandboxed WASM VM (`@arrow-js/sandbox`). The
artifact is **`app/main.ts`** (Arrow source) — see the skill-creator SKILL.md for
the full contract. This page is the quick mental model.

## The shape of a mini-app

```ts
// app/main.ts
import { reactive, html } from '@arrow-js/core'

const state = reactive({ count: 0 })

// EXPORT the template — do NOT call html`...`(el). The sandbox mounts it.
export default html`
  <button @click="${() => state.count++}">
    Clicked ${() => state.count} times
  </button>
`
```

Key rules:

- Import from the bare specifier `@arrow-js/core` — **not** a CDN URL (the VM
  provides it; a `https://…` import is an unknown module and fails).
- `export default` an `html`...`` template (or component result). Do **not** call
  `html`...`(el)` — there is no DOM mount step in a mini-app.
- `${() => expr}` for live (reactive) values; `${expr}` is evaluated once.
- `@click`, `@input`, etc. for event listeners (never `onclick`).
- Styles go in a sibling `app/main.css`.

## Getting data (the host bridge)

A mini-app has **no network and no token**. Read skill data through the host
bridge instead of `fetch`:

```ts
import { query, schema } from 'homeclaw'

// read-only SELECT, run host-side; returns the rows
const rows = await query('SELECT id, title FROM jobs ORDER BY id')

// discover tables/columns when you don't know them
const tables = await schema()
```

Send a message back to the host with `output(payload)` (a global; JSON-serializable).

## Mental model

- `reactive(obj)` — wraps a plain object, tracking reads inside `html` templates.
- `html\`...\`` — tagged template returning a renderable Arrow template.
- Callable expressions (`${() => ...}`) re-evaluate on state change; plain
  expressions (`${value}`) are evaluated once at render time.

Mini-apps only ever use `@arrow-js/core` (`reactive`, `html`, `component`,
`watch`) plus the `homeclaw` bridge. The other Arrow packages (`framework`,
`ssr`, `hydrate`) do not apply — see `advanced-ssr.md`.
