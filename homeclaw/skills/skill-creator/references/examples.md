# Arrow Examples

> **Provenance.** Forked from the official `@arrow-js/skill` package
> (`github.com/standardagents/arrow-js`, MIT) and deliberately rewritten for
> homeclaw's no-build CDN mini-app case: upstream's Vite-scaffold / SSR /
> hydration / routing examples were replaced with `@click` handlers, `db/query`
> fetches, and LAN vendoring. These examples are homeclaw-specific — do not
> re-sync them wholesale from upstream.

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

## Fetching data and rendering a list

```html
<script type="module">
  import { reactive, html } from 'https://cdn.jsdelivr.net/npm/@arrow-js/core/dist/index.mjs'

  const token = localStorage.getItem('homeclaw_token') ?? ''
  const headers = { Authorization: `Bearer ${token}` }

  const state = reactive({ items: [], loading: true, error: null })

  fetch('/api/skills/household/my-skill/db/query', {
    method: 'POST',
    headers: { ...headers, 'Content-Type': 'application/json' },
    body: JSON.stringify({ sql: 'SELECT * FROM items ORDER BY created_at DESC' })
  })
    .then(r => r.ok ? r.json() : Promise.reject(r.status))
    .then(d => { state.items = d.rows ?? []; state.loading = false })
    .catch(e => { state.error = String(e); state.loading = false })

  html`
    ${() => state.loading
      ? html`<p>Loading…</p>`
      : state.error
        ? html`<p>Error: ${() => state.error}</p>`
        : html`<ul>${() => state.items.map(item => html`<li>${item.name}</li>`)}</ul>`
    }
  `(document.body)
</script>
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
