# Arrow Getting Started

Use this reference for no-build Arrow apps (the pattern used in skill mini-apps).

## No-build pattern (for skill mini-apps)

Load Arrow.js directly from CDN — no build step, no npm:

```html
<script type="module">
  import { reactive, html } from 'https://cdn.jsdelivr.net/npm/@arrow-js/core/dist/index.mjs'

  const state = reactive({ count: 0 })

  html`
    <button @click="${() => state.count++}">
      Clicked ${() => state.count} times
    </button>
  `(document.body)
</script>
```

Key rules for no-build Arrow:
- Use `<script type="module">` for ESM imports
- Mount with `html\`...\`(document.body)` or any DOM element
- `${() => expr}` for live (reactive) values, `${expr}` for static
- `@click`, `@input`, etc. for event listeners

## LAN-only installs

If the homeclaw instance has no internet access, vendor Arrow.js:

```
skill_edit_file(name="my-skill", file="assets/arrow.js", content="<paste CDN bundle here>")
```

Then use a relative import:

```js
import { reactive, html } from './arrow.js'
```

## Mental model

- `reactive(obj)` — wraps a plain object, tracking reads inside `html` templates
- `html\`...\`` — tagged template that returns a renderable Arrow template
- Callable expressions (`${() => ...}`) are re-evaluated on state change
- Plain expressions (`${value}`) are evaluated once at render time

Mini-apps only ever use `@arrow-js/core` (`reactive`, `html`, `component`, `watch`).
The other Arrow packages (`framework`, `ssr`, `hydrate`) require a build step and do
not apply here — see `advanced-ssr.md`.
