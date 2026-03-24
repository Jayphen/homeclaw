<script lang="ts">
  import { api } from "$lib/api";

  export interface EnvEntry {
    key: string;
    value: string;
    isSet: boolean;
    dirty: boolean;
  }

  interface Props {
    /** GET endpoint that returns { entries: [{key, is_set}], env_hints?: string[] } */
    fetchUrl: string;
    /** PUT endpoint that accepts { entries: [{key, value}] } */
    saveUrl: string;
    /** Show header bar with title and close button */
    showHeader?: boolean;
    /** Callback when close is clicked (only if showHeader is true) */
    onclose?: () => void;
  }

  let { fetchUrl, saveUrl, showHeader = false, onclose }: Props = $props();

  let entries: EnvEntry[] = $state([]);
  let hints: string[] = $state([]);
  let loaded: boolean = $state(false);
  let saving: boolean = $state(false);
  let saved: boolean = $state(false);
  let error: string | null = $state(null);

  const ENV_KEY_RE = /^[A-Za-z_][A-Za-z0-9_]*$/;

  function invalidKeys(): string[] {
    return entries
      .filter(e => e.key.trim() && !ENV_KEY_RE.test(e.key.trim()))
      .map(e => e.key.trim());
  }

  function duplicateKeys(): string[] {
    const seen = new Map<string, number>();
    for (const e of entries) {
      const k = e.key.trim();
      if (k) seen.set(k, (seen.get(k) ?? 0) + 1);
    }
    return [...seen.entries()].filter(([, c]) => c > 1).map(([k]) => k);
  }

  let validationErrors = $derived.by(() => {
    const invalid = invalidKeys();
    const dupes = duplicateKeys();
    const msgs: string[] = [];
    if (invalid.length) msgs.push(`Invalid key${invalid.length > 1 ? "s" : ""}: ${invalid.join(", ")}`);
    if (dupes.length) msgs.push(`Duplicate key${dupes.length > 1 ? "s" : ""}: ${dupes.join(", ")}`);
    return msgs;
  });

  async function load() {
    try {
      const r = await api(fetchUrl);
      if (!r.ok) return;
      const data = await r.json();

      // Normalize: plugins return { entries, env_hints }, skills return { entries, is_env }
      const raw = (data.entries ?? []) as { key: string; is_set: boolean }[];
      hints = (data.env_hints ?? []) as string[];

      entries = raw.map(e => ({ key: e.key, value: "", isSet: e.is_set, dirty: false }));

      // Add rows for hinted vars not already present
      const existing = new Set(entries.map(e => e.key));
      for (const h of hints) {
        if (!existing.has(h)) entries.push({ key: h, value: "", isSet: false, dirty: false });
      }

      if (entries.length === 0) entries.push({ key: "", value: "", isSet: false, dirty: true });
      loaded = true;
    } catch {}
  }

  async function save() {
    if (validationErrors.length) return;
    saving = true;
    error = null;
    try {
      const payload = entries
        .filter(e => e.key.trim())
        .map(e => ({ key: e.key, value: e.dirty ? e.value : null }));
      const r = await api(saveUrl, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ entries: payload }),
      });
      if (!r.ok) {
        const b = await r.json().catch(() => ({}));
        error = b.detail ?? `Failed to save (${r.status})`;
        return;
      }
      entries = entries.map(e => ({
        ...e,
        isSet: e.dirty ? !!e.value : e.isSet,
        dirty: false,
        value: "",
      }));
      saved = true;
      setTimeout(() => { saved = false; }, 2000);
    } catch (e: any) {
      error = e.message;
    } finally {
      saving = false;
    }
  }

  function addRow() {
    entries = [...entries, { key: "", value: "", isSet: false, dirty: true }];
  }

  function removeRow(idx: number) {
    entries = entries.filter((_, i) => i !== idx);
    if (entries.length === 0) entries.push({ key: "", value: "", isSet: false, dirty: true });
  }

  function update(idx: number, field: "key" | "value", val: string) {
    entries = entries.map((e, i) => i === idx ? { ...e, [field]: val, dirty: true } : e);
  }

  $effect(() => { load(); });
</script>

<div class="env-editor">
  {#if showHeader}
    <div class="env-header">
      <span class="env-title">.env</span>
      {#if onclose}
        <button class="btn-link" onclick={onclose}>Close</button>
      {/if}
    </div>
  {/if}

  {#if loaded}
    {#each entries as entry, idx}
      <div class="env-row">
        <input
          class="env-key"
          class:env-key-error={entry.key.trim() !== "" && !ENV_KEY_RE.test(entry.key.trim())}
          type="text"
          value={entry.key}
          placeholder="KEY"
          oninput={(e) => update(idx, "key", e.currentTarget.value)}
        />
        <span class="env-eq">=</span>
        <input
          class="env-val"
          type="password"
          value={entry.value}
          placeholder={entry.isSet && !entry.dirty ? "configured" : ""}
          oninput={(e) => update(idx, "value", e.currentTarget.value)}
        />
        <button class="env-remove" onclick={() => removeRow(idx)} title="Remove">&times;</button>
      </div>
    {/each}

    {#if validationErrors.length}
      <div class="env-validation">{validationErrors.join(". ")}</div>
    {/if}

    {#if error}
      <div class="env-error">{error}</div>
    {/if}

    <div class="env-actions">
      <button class="btn-link" onclick={addRow}>+ Add variable</button>
      <button
        class="btn btn-primary btn-sm"
        onclick={save}
        disabled={saving || validationErrors.length > 0}
      >
        {#if saving}Saving...{:else if saved}Saved{:else}Save{/if}
      </button>
    </div>
  {/if}
</div>

<style>
  .env-editor {
    padding: 0.25rem 0;
  }
  .env-header {
    display: flex; align-items: center; justify-content: space-between;
    margin-bottom: 0.5rem;
  }
  .env-title {
    font-family: monospace; font-size: 0.78rem; font-weight: 600; color: var(--text-muted);
  }
  .env-row {
    display: flex; align-items: center; gap: 0.3rem; margin-bottom: 0.35rem;
  }
  .env-key {
    width: 40%; padding: 0.3rem 0.5rem; border: 1px solid var(--border);
    border-radius: var(--radius-sm); font-family: monospace; font-size: 0.78rem;
    background: var(--surface-low); color: var(--text);
  }
  .env-key-error {
    border-color: var(--secondary);
  }
  .env-key:focus, .env-val:focus { outline: none; border-color: var(--primary); }
  .env-eq { color: var(--text-muted); font-family: monospace; font-size: 0.82rem; flex-shrink: 0; }
  .env-val {
    flex: 1; padding: 0.3rem 0.5rem; border: 1px solid var(--border);
    border-radius: var(--radius-sm); font-family: monospace; font-size: 0.78rem;
    background: var(--surface-low); color: var(--text);
  }
  .env-remove {
    background: none; border: none; color: var(--text-muted); font-size: 1rem;
    cursor: pointer; padding: 0 0.25rem; line-height: 1; flex-shrink: 0;
  }
  .env-remove:hover { color: var(--secondary); }
  .env-actions {
    display: flex; align-items: center; justify-content: space-between;
    margin-top: 0.35rem;
  }
  .env-validation {
    font-size: 0.75rem; color: var(--secondary); margin-top: 0.25rem;
  }
  .env-error {
    font-size: 0.75rem; color: var(--secondary); margin-top: 0.25rem;
  }
  .btn-link {
    background: none; border: none; color: var(--text-muted); font-size: 0.75rem;
    cursor: pointer; padding: 0; font-family: var(--font-sans);
  }
  .btn-link:hover { color: var(--text); }
  .btn {
    border: none; border-radius: var(--radius-pill); font-family: var(--font-sans);
    font-weight: 500; cursor: pointer; transition: filter 0.15s, opacity 0.15s; white-space: nowrap;
  }
  .btn:disabled { opacity: 0.45; cursor: default; }
  .btn-primary { background: var(--primary); color: #fff; }
  .btn-primary:not(:disabled):hover { opacity: 0.9; }
  .btn-sm { padding: 0.25rem 0.65rem; font-size: 0.75rem; }
</style>
