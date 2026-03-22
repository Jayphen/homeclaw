<script lang="ts">
  import { renderMarkdown } from "$lib/markdown";

  interface Props {
    value: string;
    disabled?: boolean;
    onchange?: (value: string) => void;
  }

  let { value = $bindable(), disabled = false, onchange }: Props = $props();

  let showPreview: boolean = $state(false);
  let textarea: HTMLTextAreaElement | undefined = $state();

  function rendered(): string {
    return renderMarkdown(value);
  }

  type WrapAction = { prefix: string; suffix: string };
  type LineAction = { linePrefix: string };
  type Action = WrapAction | LineAction;

  const actions: Record<string, Action> = {
    bold: { prefix: "**", suffix: "**" },
    italic: { prefix: "_", suffix: "_" },
    code: { prefix: "`", suffix: "`" },
    heading: { linePrefix: "## " },
    ul: { linePrefix: "- " },
    ol: { linePrefix: "1. " },
    link: { prefix: "[", suffix: "](url)" },
    quote: { linePrefix: "> " },
  };

  function applyAction(name: string) {
    if (!textarea || disabled) return;
    const action = actions[name];
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const selected = value.slice(start, end);

    if ("linePrefix" in action) {
      // Find start of current line
      const lineStart = value.lastIndexOf("\n", start - 1) + 1;
      const before = value.slice(0, lineStart);
      const lineContent = value.slice(lineStart);
      value = before + action.linePrefix + lineContent;
      onchange?.(value);
      // Place cursor after prefix
      tick(() => {
        textarea!.selectionStart = start + action.linePrefix.length;
        textarea!.selectionEnd = end + action.linePrefix.length;
        textarea!.focus();
      });
    } else {
      const replacement = action.prefix + (selected || "text") + action.suffix;
      value = value.slice(0, start) + replacement + value.slice(end);
      onchange?.(value);
      tick(() => {
        if (selected) {
          textarea!.selectionStart = start + action.prefix.length;
          textarea!.selectionEnd = start + action.prefix.length + selected.length;
        } else {
          textarea!.selectionStart = start + action.prefix.length;
          textarea!.selectionEnd = start + action.prefix.length + 4; // "text"
        }
        textarea!.focus();
      });
    }
  }

  function tick(fn: () => void) {
    requestAnimationFrame(fn);
  }

  function handleKeydown(e: KeyboardEvent) {
    if (disabled) return;
    const mod = e.metaKey || e.ctrlKey;
    if (!mod) return;

    const key = e.key.toLowerCase();
    if (key === "b") { e.preventDefault(); applyAction("bold"); }
    else if (key === "i") { e.preventDefault(); applyAction("italic"); }
    else if (key === "k") { e.preventDefault(); applyAction("link"); }
    else if (key === "e") { e.preventDefault(); applyAction("code"); }
  }

  interface ToolbarItem {
    name: string;
    label: string;
    icon: string;
    shortcut?: string;
  }

  const toolbarItems: ToolbarItem[] = [
    { name: "bold", label: "Bold", icon: "B", shortcut: "⌘B" },
    { name: "italic", label: "Italic", icon: "I", shortcut: "⌘I" },
    { name: "code", label: "Code", icon: "<>", shortcut: "⌘E" },
    { name: "heading", label: "Heading", icon: "H" },
    { name: "ul", label: "Bullet list", icon: "•" },
    { name: "ol", label: "Numbered list", icon: "1." },
    { name: "link", label: "Link", icon: "🔗", shortcut: "⌘K" },
    { name: "quote", label: "Blockquote", icon: "❝" },
  ];
</script>

<div class="md-editor" class:disabled>
  <div class="md-toolbar">
    <div class="md-toolbar-actions">
      {#each toolbarItems as item}
        <button
          class="md-tool"
          title={item.shortcut ? `${item.label} (${item.shortcut})` : item.label}
          onclick={() => applyAction(item.name)}
          {disabled}
          type="button"
        >
          <span class="md-tool-icon" class:md-tool-bold={item.name === "bold"} class:md-tool-italic={item.name === "italic"}>{item.icon}</span>
        </button>
      {/each}
    </div>
    <button
      class="md-preview-toggle"
      class:active={showPreview}
      onclick={() => (showPreview = !showPreview)}
      type="button"
    >
      {showPreview ? "Edit" : "Preview"}
    </button>
  </div>

  {#if showPreview}
    <div class="md-preview note-body">
      {#if value.trim()}
        {@html rendered()}
      {:else}
        <p class="md-preview-empty">Nothing to preview</p>
      {/if}
    </div>
  {:else}
    <textarea
      class="md-textarea"
      bind:this={textarea}
      bind:value
      onkeydown={handleKeydown}
      oninput={() => onchange?.(value)}
      {disabled}
      placeholder="Write in markdown…"
    ></textarea>
  {/if}
</div>

<style>
  .md-editor {
    border: none;
    border-radius: var(--radius-sm);
    overflow: hidden;
    background: var(--surface-low);
  }

  .md-editor.disabled {
    opacity: 0.5;
    pointer-events: none;
  }

  /* ---- Toolbar ---- */
  .md-toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.3rem 0.5rem;
    background: var(--surface-low);
  }

  .md-toolbar-actions {
    display: flex;
    gap: 0.15rem;
  }

  .md-tool {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    border: none;
    border-radius: var(--radius-sm);
    background: none;
    color: var(--text-muted);
    cursor: pointer;
    font-size: 0.78rem;
    transition: background 0.12s, color 0.12s;
  }

  .md-tool:hover {
    background: var(--surface);
    color: var(--text);
  }

  .md-tool-icon {
    line-height: 1;
  }

  .md-tool-bold {
    font-weight: 700;
    font-size: 0.85rem;
  }

  .md-tool-italic {
    font-style: italic;
    font-family: var(--font-serif);
    font-size: 0.85rem;
  }

  .md-preview-toggle {
    border: none;
    background: none;
    color: var(--text-muted);
    font-size: 0.75rem;
    cursor: pointer;
    padding: 0.25rem 0.5rem;
    border-radius: var(--radius-sm);
    transition: background 0.12s, color 0.12s;
  }

  .md-preview-toggle:hover,
  .md-preview-toggle.active {
    background: var(--surface);
    color: var(--text);
  }

  /* ---- Textarea ---- */
  .md-textarea {
    display: block;
    width: 100%;
    min-height: 400px;
    padding: 0.75rem;
    border: none;
    font-family: ui-monospace, "Cascadia Code", "Fira Code", Menlo, monospace;
    font-size: 0.88rem;
    line-height: 1.6;
    color: var(--text);
    background: var(--bg);
    resize: vertical;
    box-sizing: border-box;
    outline: none;
  }

  .md-textarea::placeholder {
    color: var(--text-muted);
    opacity: 0.6;
  }

  /* ---- Preview ---- */
  .md-preview {
    min-height: 400px;
    padding: 0.75rem;
    font-size: 0.92rem;
    line-height: 1.65;
    color: var(--text);
    background: var(--surface);
  }

  .md-preview-empty {
    color: var(--text-muted);
    font-style: italic;
  }
</style>
