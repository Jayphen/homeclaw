<script lang="ts">
  import { api } from "$lib/api";
  import { formatRelativeTime } from "$lib/time";

  interface Routine {
    name: string;
    description: string;
    trigger_type: string;
    trigger_kwargs: Record<string, string | number>;
    last_run: string | null;
    next_run: string | null;
  }

  let routines: Routine[] = $state([]);
  let loading: boolean = $state(true);
  let error: string | null = $state(null);

  // Add form
  let showAdd: boolean = $state(false);
  let addTitle: string = $state("");
  let addSchedule: string = $state("");
  let addAction: string = $state("");
  let addError: string | null = $state(null);
  let addSaving: boolean = $state(false);

  // Running
  let runningName: string | null = $state(null);

  async function load() {
    try {
      const r = await api("/api/routines");
      if (!r.ok) throw new Error(`${r.status}`);
      const data = await r.json();
      routines = data.routines;
      loading = false;
    } catch (e: any) {
      error = e.message;
      loading = false;
    }
  }

  async function handleAdd() {
    addError = null;
    if (!addTitle.trim() || !addSchedule.trim() || !addAction.trim()) {
      addError = "All fields are required.";
      return;
    }
    addSaving = true;
    try {
      const r = await api("/api/routines", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: addTitle.trim(),
          schedule: addSchedule.trim(),
          action: addAction.trim(),
        }),
      });
      if (!r.ok) {
        const data = await r.json();
        addError = data.detail || `Error ${r.status}`;
        addSaving = false;
        return;
      }
      addTitle = "";
      addSchedule = "";
      addAction = "";
      showAdd = false;
      await load();
    } catch (e: any) {
      addError = e.message;
    }
    addSaving = false;
  }

  async function handleDelete(name: string) {
    if (!confirm(`Remove routine "${name}"?`)) return;
    await api(`/api/routines/${encodeURIComponent(name)}`, { method: "DELETE" });
    await load();
  }

  async function handleRun(name: string) {
    runningName = name;
    try {
      await api(`/api/routines/${encodeURIComponent(name)}/run`, { method: "POST" });
      await load();
    } catch {
      // ignore
    }
    runningName = null;
  }

  function formatSchedule(r: Routine): string {
    const kw = r.trigger_kwargs;
    if (r.trigger_type === "cron") {
      const parts: string[] = [];
      if (kw.day_of_week && kw.day_of_week !== "*") parts.push(`${kw.day_of_week}`);
      if (kw.hour !== undefined) {
        const h = Number(kw.hour);
        const m = kw.minute !== undefined ? String(kw.minute).padStart(2, "0") : "00";
        const ampm = h >= 12 ? "pm" : "am";
        const h12 = h % 12 || 12;
        parts.push(`${h12}:${m}${ampm}`);
      }
      if (kw.day && kw.day !== "*") parts.push(`day ${kw.day}`);
      return parts.join(" at ") || "cron";
    }
    if (r.trigger_type === "interval") {
      const parts: string[] = [];
      if (kw.weeks) parts.push(`${kw.weeks} week${Number(kw.weeks) !== 1 ? "s" : ""}`);
      if (kw.days) parts.push(`${kw.days} day${Number(kw.days) !== 1 ? "s" : ""}`);
      if (kw.hours) parts.push(`${kw.hours}h`);
      if (kw.minutes) parts.push(`${kw.minutes}m`);
      return `every ${parts.join(" ")}`;
    }
    return r.trigger_type;
  }

  $effect(() => {
    load();
  });
</script>

{#if loading}
  <div class="loading">
    <div class="loading-dot"></div>
    <div class="loading-dot"></div>
    <div class="loading-dot"></div>
  </div>
{:else if error}
  <div class="error-card">
    <p>Couldn't load routines.</p>
    <small>{error}</small>
  </div>
{:else}
  <header class="page-header">
    <div class="header-row">
      <h1>Routines</h1>
      <button class="add-btn" onclick={() => { showAdd = !showAdd; }}>
        {showAdd ? "Cancel" : "+ Add routine"}
      </button>
    </div>
    <p class="subtitle">Scheduled tasks homeclaw runs automatically.</p>
  </header>

  {#if showAdd}
    <section class="card add-form">
      <h2>New routine</h2>
      {#if addError}
        <div class="form-error">{addError}</div>
      {/if}
      <div class="field">
        <label for="add-title">Title</label>
        <input id="add-title" type="text" bind:value={addTitle} placeholder="e.g. Morning briefing" />
      </div>
      <div class="field">
        <label for="add-schedule">Schedule</label>
        <input id="add-schedule" type="text" bind:value={addSchedule} placeholder="e.g. Every weekday at 7:30am" />
        <span class="field-hint">Natural language or 5-field cron expression</span>
      </div>
      <div class="field">
        <label for="add-action">Action</label>
        <textarea id="add-action" bind:value={addAction} placeholder="What should homeclaw do?" rows="2"></textarea>
      </div>
      <button class="save-btn" onclick={handleAdd} disabled={addSaving}>
        {addSaving ? "Adding..." : "Add routine"}
      </button>
    </section>
  {/if}

  {#if routines.length === 0}
    <div class="empty">
      <p>No routines yet.</p>
      <small>Add a routine above, or ask homeclaw in chat to set one up.</small>
    </div>
  {:else}
    <div class="routine-list">
      {#each routines as routine, i}
        <div class="routine-card">
          <div class="routine-header">
            <div class="routine-title-row">
              <span class="routine-name">{routine.description.split(":")[0]}</span>
              <span class="schedule-badge">{formatSchedule(routine)}</span>
            </div>
            <div class="routine-actions">
              <button
                class="run-btn"
                onclick={() => handleRun(routine.name)}
                disabled={runningName === routine.name}
              >
                {runningName === routine.name ? "Running..." : "Run now"}
              </button>
              <button class="delete-btn" onclick={() => handleDelete(routine.name)}>
                Remove
              </button>
            </div>
          </div>
          {#if routine.description.includes(":")}
            <p class="routine-desc">{routine.description.split(":").slice(1).join(":").trim()}</p>
          {/if}
          <div class="routine-meta">
            {#if routine.last_run}
              <span class="meta-item">Last ran {formatRelativeTime(routine.last_run)}</span>
            {:else}
              <span class="meta-item">Never run</span>
            {/if}
            {#if routine.next_run}
              <span class="meta-item">Next: {new Date(routine.next_run).toLocaleString("en-GB", { weekday: "short", hour: "2-digit", minute: "2-digit", hour12: false })}</span>
            {/if}
          </div>
        </div>
      {/each}
    </div>
  {/if}
{/if}

<style>
  .loading {
    display: flex;
    justify-content: center;
    gap: 0.5rem;
    padding: 4rem 0;
  }

  .loading-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--primary);
    opacity: 0.3;
    animation: pulse 1s ease-in-out infinite;
  }

  .loading-dot:nth-child(2) { animation-delay: 0.15s; }
  .loading-dot:nth-child(3) { animation-delay: 0.3s; }

  @keyframes pulse {
    0%, 100% { opacity: 0.3; transform: scale(1); }
    50% { opacity: 1; transform: scale(1.2); }
  }

  .error-card {
    background: #fef2f0;
    border-radius: var(--radius);
    padding: 1.5rem;
    text-align: center;
    color: var(--secondary);
  }

  .error-card p { margin: 0 0 0.5rem; font-weight: 500; }
  .error-card small { color: var(--text-muted); }

  /* ---- Header ---- */
  .page-header {
    margin-bottom: 2rem;
  }

  .header-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
  }

  .page-header h1 {
    font-family: var(--font-serif);
    font-weight: 600;
    font-size: 2rem;
    margin: 0;
    color: var(--text);
    letter-spacing: -0.02em;
  }

  .subtitle {
    font-size: 0.88rem;
    color: var(--text-muted);
    margin: 0.25rem 0 0;
  }

  .add-btn {
    padding: 0.4rem 0.9rem;
    border: none;
    border-radius: var(--radius-pill);
    background: linear-gradient(135deg, var(--primary), var(--primary-container));
    color: var(--on-primary);
    font-size: 0.82rem;
    font-weight: 600;
    font-family: var(--font-sans);
    cursor: pointer;
    transition: filter 0.15s;
    white-space: nowrap;
  }

  .add-btn:hover { filter: brightness(1.08); }

  /* ---- Add form ---- */
  .add-form {
    background: var(--surface);
    border-radius: var(--radius);
    padding: 1.5rem;
    margin-bottom: 2rem;
    box-shadow: var(--shadow);
  }

  .add-form h2 {
    font-family: var(--font-serif);
    font-weight: 600;
    font-size: 1rem;
    margin: 0 0 1rem;
    color: var(--text);
  }

  .field {
    margin-bottom: 0.75rem;
  }

  .field label {
    display: block;
    font-size: 0.82rem;
    font-weight: 600;
    color: var(--text);
    margin-bottom: 0.3rem;
  }

  .field input,
  .field textarea {
    width: 100%;
    padding: 0.5rem 0.75rem;
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    font-size: 0.85rem;
    font-family: var(--font-sans);
    background: var(--surface-low);
    color: var(--text);
    resize: vertical;
  }

  .field input:focus,
  .field textarea:focus {
    outline: none;
    border-color: var(--primary);
  }

  .field-hint {
    display: block;
    font-size: 0.72rem;
    color: var(--text-muted);
    margin-top: 0.2rem;
  }

  .form-error {
    background: #fef2f0;
    border-radius: var(--radius-sm);
    padding: 0.4rem 0.65rem;
    font-size: 0.82rem;
    color: var(--secondary);
    margin-bottom: 0.75rem;
  }

  .save-btn {
    padding: 0.5rem 1.2rem;
    border: none;
    border-radius: var(--radius-pill);
    background: linear-gradient(135deg, var(--primary), var(--primary-container));
    color: var(--on-primary);
    font-size: 0.85rem;
    font-weight: 600;
    font-family: var(--font-sans);
    cursor: pointer;
    transition: filter 0.15s;
  }

  .save-btn:hover { filter: brightness(1.08); }
  .save-btn:disabled { opacity: 0.5; cursor: default; }

  /* ---- Routine list ---- */
  .routine-list {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .routine-card {
    background: var(--surface);
    border-radius: var(--radius);
    padding: 1.25rem 1.5rem;
    box-shadow: var(--shadow);
    transition: background 0.2s, box-shadow 0.2s;
  }

  .routine-card:hover {
    background: var(--surface-bright);
    box-shadow: 0 0 0 1px rgba(198, 200, 184, 0.2), var(--shadow);
  }

  .routine-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 1rem;
  }

  .routine-title-row {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    flex-wrap: wrap;
  }

  .routine-name {
    font-weight: 600;
    font-size: 0.92rem;
    color: var(--text);
  }

  .schedule-badge {
    font-size: 0.7rem;
    font-weight: 600;
    padding: 0.15rem 0.5rem;
    border-radius: var(--radius-pill);
    background: var(--surface-low);
    color: var(--primary);
    letter-spacing: 0.02em;
    white-space: nowrap;
  }

  .routine-actions {
    display: flex;
    gap: 0.35rem;
    flex-shrink: 0;
  }

  .run-btn {
    padding: 0.3rem 0.65rem;
    border: none;
    border-radius: var(--radius-pill);
    background: var(--surface-low);
    color: var(--text-muted);
    font-size: 0.75rem;
    font-weight: 500;
    font-family: var(--font-sans);
    cursor: pointer;
    transition: background 0.15s, color 0.15s;
  }

  .run-btn:hover:not(:disabled) {
    background: var(--primary);
    color: var(--on-primary);
  }

  .run-btn:disabled { opacity: 0.5; cursor: default; }

  .delete-btn {
    padding: 0.3rem 0.65rem;
    border: none;
    border-radius: var(--radius-pill);
    background: var(--surface-low);
    color: var(--text-muted);
    font-size: 0.75rem;
    font-weight: 500;
    font-family: var(--font-sans);
    cursor: pointer;
    transition: background 0.15s, color 0.15s;
  }

  .delete-btn:hover {
    background: var(--secondary);
    color: var(--on-secondary);
  }

  .routine-desc {
    font-size: 0.85rem;
    color: var(--text-muted);
    margin: 0.4rem 0 0;
    line-height: 1.5;
  }

  .routine-meta {
    display: flex;
    align-items: center;
    gap: 1rem;
    margin-top: 0.5rem;
  }

  .meta-item {
    font-size: 0.72rem;
    color: var(--text-muted);
  }

  /* ---- Empty ---- */
  .empty {
    text-align: center;
    padding: 3rem 1rem;
    color: var(--text-muted);
  }

  .empty p {
    font-family: var(--font-serif);
    font-style: italic;
    font-size: 1.1rem;
    margin: 0 0 0.5rem;
  }

  .empty small { font-size: 0.82rem; }
</style>
