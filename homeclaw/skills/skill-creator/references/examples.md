# Arrow Examples

> **homeclaw mini-apps run in a sandbox** (`@arrow-js/sandbox`). Import from the
> bare `@arrow-js/core`, `export default` your template (no `html`...`(el)` mount),
> and read data via the `homeclaw` host bridge — never `fetch`/`localStorage`.
> See the skill-creator SKILL.md for the full contract. The Arrow patterns below
> (state, events, keyed lists, components) are correct; ignore any older
> CDN/mount framing.

## Counter

```ts
import { html, reactive } from '@arrow-js/core'

const state = reactive({ count: 0 })

html`
  <button @click="${() => state.count++}">
    Clicked ${() => state.count} times
  </button>
`
```

## Component composition

```ts
import { component, html, reactive } from '@arrow-js/core'

const Counter = component((props) =>
  html`<strong>${() => props.count}</strong>`
)

const state = reactive({ count: 1 })

html`<p>Current count: ${Counter(state)}</p>`
```

## Fetching data and rendering a list (via the host bridge)

```ts
// app/main.ts
import { reactive, html } from '@arrow-js/core'
import { query } from 'homeclaw'

const state = reactive({ items: [], loading: true, error: null })

// Read-only SELECT, run host-side. Surface failures into state.error — never
// swallow them into an empty list.
query('SELECT id, name FROM items ORDER BY created_at DESC')
  .then((rows) => { state.items = rows; state.loading = false })
  .catch((e) => { state.error = String(e?.message ?? e); state.loading = false })

export default html`
  ${() => state.loading
    ? html`<p>Loading…</p>`
    : state.error
      ? html`<p>Error: ${() => state.error}</p>`
      : html`<ul>${() => state.items.map(item => html`<li>${() => item.name}</li>`.key(item.id))}</ul>`
  }
`
```

## Event handlers

```html
<!-- @click passes a callable -->
html`<button @click="${() => state.count++}">+</button>`

<!-- For async handlers -->
html`<button @click="${async () => { await save(); state.status = 'saved' }}">Save</button>`
```

## Conditional rendering

```js
html`
  ${() => state.open
    ? html`<div class="panel">${() => state.content}</div>`
    : ''
  }
`
```

## Keyed lists (stable DOM identity)

```js
html`
  <ul>
    ${() => state.items.map(item =>
      html`<li>${item.name}</li>`.key(item.id)
    )}
  </ul>
`
```
