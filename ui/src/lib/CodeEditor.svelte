<script lang="ts">
  interface Props {
    value: string;
    disabled?: boolean;
    language?: string;
    onchange?: (value: string) => void;
  }

  let { value = $bindable(), disabled = false, language = "", onchange }: Props = $props();
</script>

<div class="code-editor" class:disabled>
  <div class="code-toolbar">
    <span class="code-lang">{language || "plain text"}</span>
  </div>
  <textarea
    class="code-textarea"
    bind:value
    oninput={() => onchange?.(value)}
    {disabled}
    placeholder="Edit file…"
    spellcheck="false"
  ></textarea>
</div>

<style>
  .code-editor {
    border: 1px solid var(--border);
    border-radius: var(--radius);
    overflow: hidden;
    background: var(--bg);
  }

  .code-editor.disabled {
    opacity: 0.5;
    pointer-events: none;
  }

  .code-toolbar {
    display: flex;
    align-items: center;
    padding: 0.3rem 0.6rem;
    border-bottom: 1px solid var(--border);
    background: var(--surface);
  }

  .code-lang {
    font-size: 0.72rem;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.03em;
  }

  .code-textarea {
    display: block;
    width: 100%;
    min-height: 400px;
    padding: 0.75rem;
    border: none;
    font-family: ui-monospace, "Cascadia Code", "Fira Code", Menlo, monospace;
    font-size: 0.85rem;
    line-height: 1.55;
    tab-size: 2;
    color: var(--text);
    background: var(--bg);
    resize: vertical;
    box-sizing: border-box;
    outline: none;
    white-space: pre;
    overflow-wrap: normal;
    overflow-x: auto;
  }

  .code-textarea::placeholder {
    color: var(--text-muted);
    opacity: 0.6;
  }
</style>
