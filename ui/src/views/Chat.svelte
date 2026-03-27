<script lang="ts">
  import { privateChat, householdChat, loadHistory, type ChatTab } from "$lib/chat";
  import { renderMarkdown } from "$lib/markdown";
  import { onMount, tick } from "svelte";

  let activeTab: ChatTab = $state("private");

  let chat = $derived(activeTab === "household" ? householdChat : privateChat);

  onMount(() => { loadHistory("private"); loadHistory("household"); });

  function switchTab(tab: ChatTab) {
    activeTab = tab;
    loadHistory(tab);
  }

  let inputText = $state("");
  let messagesEl: HTMLElement | undefined = $state();
  let showDebug = $state(false);
  let expandedDebug: Set<string> = $state(new Set());

  interface DebugMeta {
    model?: string;
    tools?: string[];
    tool_rounds?: number;
    duration_ms?: number;
  }

  const DEBUG_RE = /\n?<!--debug:(.*?)-->$/;

  function parseMessage(message: (typeof chat.messages)[0]): {
    text: string;
    debug: DebugMeta | null;
  } {
    const raw = message.parts
      .filter((p): p is { type: "text"; text: string } => p.type === "text")
      .map((p) => p.text)
      .join("");
    const m = raw.match(DEBUG_RE);
    if (!m) return { text: raw, debug: null };
    try {
      return { text: raw.replace(DEBUG_RE, ""), debug: JSON.parse(m[1]) };
    } catch {
      return { text: raw, debug: null };
    }
  }

  function toggleDebug(id: string) {
    const next = new Set(expandedDebug);
    if (next.has(id)) next.delete(id); else next.add(id);
    expandedDebug = next;
  }

  function scrollToBottom() {
    tick().then(() => {
      if (messagesEl) {
        messagesEl.scrollTop = messagesEl.scrollHeight;
      }
    });
  }

  $effect(() => {
    chat.messages.length;
    chat.status;
    scrollToBottom();
  });

  async function send() {
    const text = inputText.trim();
    if (!text || chat.status === "submitted" || chat.status === "streaming") return;
    inputText = "";
    await chat.sendMessage({ text });
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  }
</script>

<div class="chat">
  <div class="chat-header">
    <div class="tab-bar">
      <button
        class="tab"
        class:active={activeTab === "private"}
        onclick={() => switchTab("private")}
      >Private</button>
      <button
        class="tab"
        class:active={activeTab === "household"}
        onclick={() => switchTab("household")}
      >Household</button>
    </div>
    <button
      class="debug-toggle"
      class:active={showDebug}
      onclick={() => { showDebug = !showDebug; }}
      title="Show debug info"
    >debug</button>
  </div>

  <div class="messages" bind:this={messagesEl}>
    {#if chat.messages.length === 0}
      <div class="empty">
        <p class="empty-title">What can I help with?</p>
        <p class="empty-hint">
          Ask about your household, contacts, bookmarks, schedules, or anything
          else.
        </p>
      </div>
    {/if}

    {#each chat.messages as message (message.id)}
      {@const parsed = parseMessage(message)}
      <div class="message message-{message.role}">
        <div class="bubble bubble-{message.role}">
          {#if message.role === "user"}
            <p>{parsed.text}</p>
          {:else}
            {@html renderMarkdown(parsed.text)}
          {/if}
        </div>
        {#if showDebug && message.role === "assistant" && parsed.debug}
          <button
            class="debug-badge"
            onclick={() => toggleDebug(message.id)}
          >
            {parsed.debug.model?.split('/').pop() ?? '?'}
            {#if parsed.debug.tools?.length}
              &middot; {parsed.debug.tools.length} tool{parsed.debug.tools.length === 1 ? '' : 's'}
            {/if}
            &middot; {((parsed.debug.duration_ms ?? 0) / 1000).toFixed(1)}s
          </button>
          {#if expandedDebug.has(message.id)}
            <div class="debug-panel">
              <div><strong>Model</strong> {parsed.debug.model ?? 'unknown'}</div>
              {#if parsed.debug.tool_rounds}
                <div><strong>Tool rounds</strong> {parsed.debug.tool_rounds}</div>
              {/if}
              {#if parsed.debug.tools?.length}
                <div><strong>Tools</strong> {parsed.debug.tools.join(', ')}</div>
              {/if}
              <div><strong>Duration</strong> {((parsed.debug.duration_ms ?? 0) / 1000).toFixed(1)}s</div>
            </div>
          {/if}
        {/if}
      </div>
    {/each}

    {#if chat.status === "submitted"}
      <div class="message message-assistant">
        <div class="bubble bubble-assistant">
          <span class="thinking">Thinking<span class="dots"></span></span>
        </div>
      </div>
    {/if}

    {#if chat.error}
      <div class="message message-error">
        <div class="bubble bubble-error">
          Something went wrong. Try again.
        </div>
      </div>
    {/if}
  </div>

  <div class="input-area">
    <div class="input-row">
      <textarea
        bind:value={inputText}
        onkeydown={handleKeydown}
        placeholder="Message homeclaw..."
        rows="1"
        disabled={chat.status === "submitted" || chat.status === "streaming"}
      ></textarea>
      <button
        class="send-btn"
        onclick={send}
        disabled={!inputText.trim() ||
          chat.status === "submitted" ||
          chat.status === "streaming"}
        aria-label="Send"
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" />
        </svg>
      </button>
    </div>
  </div>
</div>

<style>
  .chat {
    display: flex;
    flex-direction: column;
    height: calc(100vh - 5.5rem);
    max-height: calc(100vh - 5.5rem);
  }

  .chat-header {
    flex-shrink: 0;
    padding-bottom: 0.5rem;
    display: flex;
    align-items: baseline;
    gap: 0.75rem;
  }

  .tab-bar {
    display: flex;
    gap: 0.25rem;
    background: var(--surface-low);
    border-radius: var(--radius-sm);
    padding: 0.2rem;
  }

  .tab {
    font-family: var(--font-sans);
    font-size: 0.82rem;
    font-weight: 500;
    color: var(--text-muted);
    background: none;
    border: none;
    border-radius: calc(var(--radius-sm) - 0.1rem);
    padding: 0.3rem 0.85rem;
    cursor: pointer;
    transition: color 0.15s, background 0.15s;
  }

  .tab:hover { color: var(--text); }

  .tab.active {
    color: var(--text);
    background: var(--surface);
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
  }

  .debug-toggle {
    font-family: var(--font-sans);
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-muted);
    background: none;
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    padding: 0.2rem 0.5rem;
    cursor: pointer;
    transition: color 0.15s, border-color 0.15s;
  }

  .debug-toggle:hover { color: var(--text); border-color: var(--text-muted); }
  .debug-toggle.active { color: var(--primary); border-color: var(--primary); }

  .messages {
    flex: 1;
    overflow-y: auto;
    padding: 1rem 0;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .empty {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    color: var(--text-muted);
  }

  .empty-title {
    font-family: var(--font-serif);
    font-size: 1.25rem;
    font-weight: 600;
    color: var(--text);
    margin: 0 0 0.5rem;
  }

  .empty-hint {
    font-size: 0.85rem;
    margin: 0;
    max-width: 320px;
  }

  .message {
    display: flex;
  }

  .message-user {
    justify-content: flex-end;
  }

  .message-assistant {
    justify-content: flex-start;
  }

  .message-error {
    justify-content: center;
  }

  .bubble {
    max-width: 80%;
    padding: 0.6rem 1rem;
    border-radius: var(--radius-md);
    font-size: 0.9rem;
    line-height: 1.55;
    word-wrap: break-word;
    overflow-wrap: break-word;
  }

  .bubble-user {
    background: var(--primary);
    color: var(--on-primary);
    border-bottom-right-radius: var(--radius-sm);
  }

  .bubble-user p {
    margin: 0;
    white-space: pre-wrap;
  }

  .bubble-assistant {
    background: var(--surface);
    color: var(--text);
    border-bottom-left-radius: var(--radius-sm);
    box-shadow: var(--shadow);
  }

  .bubble-assistant :global(p) {
    margin: 0.3rem 0;
  }

  .bubble-assistant :global(p:first-child) {
    margin-top: 0;
  }

  .bubble-assistant :global(p:last-child) {
    margin-bottom: 0;
  }

  .bubble-assistant :global(code) {
    background: var(--surface-low);
    padding: 0.1em 0.35em;
    border-radius: 4px;
    font-size: 0.85em;
  }

  .bubble-assistant :global(pre) {
    background: var(--surface-low);
    padding: 0.75rem 1rem;
    border-radius: var(--radius-sm);
    overflow-x: auto;
    margin: 0.5rem 0;
  }

  .bubble-assistant :global(pre code) {
    background: none;
    padding: 0;
  }

  .bubble-assistant :global(em) {
    color: var(--text-muted);
    font-style: italic;
  }

  .bubble-assistant :global(ul),
  .bubble-assistant :global(ol) {
    margin: 0.3rem 0;
    padding-left: 1.5rem;
  }

  .bubble-assistant :global(a) {
    color: var(--primary);
  }

  .bubble-error {
    background: #fef2f0;
    color: var(--secondary);
    font-size: 0.85rem;
  }

  .debug-badge {
    display: inline-block;
    font-family: var(--font-sans);
    font-size: 0.68rem;
    color: var(--text-muted);
    background: var(--surface-low);
    border: none;
    border-radius: var(--radius-sm);
    padding: 0.15rem 0.5rem;
    margin-top: 0.25rem;
    cursor: pointer;
    transition: color 0.15s;
  }

  .debug-badge:hover { color: var(--text); }

  .debug-panel {
    font-family: var(--font-sans);
    font-size: 0.72rem;
    color: var(--text-muted);
    background: var(--surface-low);
    border-radius: var(--radius-sm);
    padding: 0.5rem 0.75rem;
    margin-top: 0.25rem;
    max-width: 80%;
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
  }

  .debug-panel strong {
    color: var(--text);
    margin-right: 0.4rem;
  }

  .thinking {
    color: var(--text-muted);
    font-size: 0.85rem;
  }

  .dots::after {
    content: "";
    animation: dots 1.4s steps(4, end) infinite;
  }

  @keyframes dots {
    0% { content: ""; }
    25% { content: "."; }
    50% { content: ".."; }
    75% { content: "..."; }
  }

  /* Input area */
  .input-area {
    flex-shrink: 0;
    padding: 0.75rem 0;
  }

  .input-row {
    display: flex;
    gap: 0.5rem;
    align-items: flex-end;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    padding: 0.5rem;
    box-shadow: var(--shadow);
  }

  .input-row textarea {
    flex: 1;
    border: none;
    background: transparent;
    font-family: var(--font-sans);
    font-size: 0.9rem;
    color: var(--text);
    resize: none;
    padding: 0.35rem 0.5rem;
    line-height: 1.5;
    max-height: 150px;
    outline: none;
  }

  .input-row textarea::placeholder {
    color: var(--text-muted);
  }

  .send-btn {
    flex-shrink: 0;
    width: 36px;
    height: 36px;
    border: none;
    border-radius: 50%;
    background: var(--primary);
    color: var(--on-primary);
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: filter 0.15s, opacity 0.15s;
  }

  .send-btn:hover:not(:disabled) {
    filter: brightness(1.1);
  }

  .send-btn:disabled {
    opacity: 0.35;
    cursor: default;
  }

  @media (max-width: 768px) {
    .chat {
      height: calc(100vh - 7rem);
      max-height: calc(100vh - 7rem);
    }
  }
</style>
