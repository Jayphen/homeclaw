// Reference mini-app for homeclaw skills — runs inside @arrow-js/sandbox.
//
// This is app/main.ts. The sandbox compiles it and runs it in a WASM VM, then
// renders the exported template inline in the homeclaw UI. The contract is the
// WHOLE API surface — follow it exactly:
//
//   1. import { reactive, html } from '@arrow-js/core'
//   2. Read skill data via the HOST BRIDGE: import { query, schema } from 'homeclaw'
//        - query(sql, params?) runs a read-only SELECT against this skill's
//          SQLite db, host-side. It returns the rows.
//        - schema() returns the tables/columns — call it if you don't know them.
//        - NEVER use fetch() and NEVER a token. The mini-app has no network and
//          no credentials; the host performs the (authenticated) call for you.
//   3. State is reactive({...}); mutate fields directly (state.loading = false).
//   4. Live values are CALLABLES: ${() => state.x}. A bare ${state.x} renders
//      once and never updates.
//   5. Events use an @-prefixed attribute: @click="${() => ...}" (NEVER onclick).
//   6. EXPORT DEFAULT an html`...` template (or component result). Do NOT call
//      html`...`(el) — the sandbox mounts the default export for you.
//   7. Send a message to the host with output(payload) when needed (output is a
//      global inside the sandbox; payload must be JSON-serializable).
//   8. Put styles in app/main.css (a sibling file).
import { reactive, html } from '@arrow-js/core'
import { query } from 'homeclaw'

interface Job {
  id: number
  title: string
  done: number
}

const state = reactive<{ rows: Job[]; loading: boolean; error: string | null }>({
  rows: [],
  loading: true,
  error: null,
})

// Load once. Surface failures into state.error — never swallow them into an
// empty list, or a broken query looks identical to "no data yet".
query('SELECT id, title, done FROM jobs ORDER BY id')
  .then((rows) => {
    state.rows = rows as Job[]
    state.loading = false
  })
  .catch((err) => {
    state.error = String((err && err.message) || err)
    state.loading = false
  })

// A keyed list row — .key(id) lets Arrow reuse nodes when the list changes.
const Row = (job: Job) =>
  html`<li class="${() => (job.done ? 'job done' : 'job')}">${() => job.title}</li>`.key(job.id)

export default html`
  <section>
    <h1>Jobs</h1>
    ${() => (state.loading ? html`<p class="status">Loading…</p>` : null)}
    ${() => (state.error ? html`<p class="error">${() => state.error}</p>` : null)}
    ${() =>
      !state.loading && !state.error && state.rows.length === 0
        ? html`<p class="status">No jobs yet.</p>`
        : null}
    ${() =>
      !state.loading && !state.error && state.rows.length > 0
        ? html`<ul>${() => state.rows.map(Row)}</ul>`
        : null}
  </section>
`
