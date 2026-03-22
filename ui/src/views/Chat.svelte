<script lang="ts">
  import { chat, loadHistory } from "$lib/chat";
  import { renderMarkdown } from "$lib/markdown";
  import { onMount, tick } from "svelte";

  onMount(() => { loadHistory(); });

  let inputText = $state("");
  let messagesEl: HTMLElement | undefined = $state();

  function scrollToBottom() {
    tick().then(() => {
      if (messagesEl) {
        messagesEl.scrollTop = messagesEl.scrollHeight;
      }
    });
  }

  // Auto-scroll when messages change
  $effect(() => {
    // Access messages to create dependency
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

  function getMessageText(message: (typeof chat.messages)[0]): string {
    return message.parts
      .filter((p): p is { type: "text"; text: string } => p.type === "text")
      .map((p) => p.text)
      .join("");
  }
</script>

<div class="chat">
  <div class="chat-header">
    <h1>Chat</h1>
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
      <div class="message message-{message.role}">
        <div class="bubble bubble-{message.role}">
          {#if message.role === "user"}
            <p>{getMessageText(message)}</p>
          {:else}
            {@html renderMarkdown(getMessageText(message))}
          {/if}
        </div>
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
  }

  .chat-header h1 {
    font-family: var(--font-serif);
    font-weight: 600;
    font-size: 1.5rem;
    color: var(--text);
    margin: 0;
  }

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
