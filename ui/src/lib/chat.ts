import { Chat, type UIMessage } from "@ai-sdk/svelte";
import { TextStreamChatTransport } from "ai";
import { api, getToken } from "$lib/api";

/** Singleton Chat instance — survives navigation between views. */
export const chat = new Chat({
  transport: new TextStreamChatTransport({
    api: "/api/chat",
    headers: () => {
      const token = getToken();
      return token ? { Authorization: `Bearer ${token}` } : {};
    },
    // Only send the latest user message — the server manages history.
    prepareSendMessagesRequest: ({ messages, headers, credentials, api: url }) => ({
      body: { messages: messages.slice(-1) },
      headers,
      credentials,
      api: url,
    }),
  }),
});

let historyLoaded = false;

/** Load recent conversation history from the backend (once). */
export async function loadHistory(): Promise<void> {
  if (historyLoaded || chat.messages.length > 0) return;
  historyLoaded = true;

  try {
    const resp = await api("/api/chat/history");
    if (!resp.ok) return;
    const data: { role: string; content: string }[] = await resp.json();
    if (!data.length) return;

    let counter = 0;
    const messages: UIMessage[] = data.map((m) => ({
      id: `hist-${counter++}`,
      role: m.role as "user" | "assistant",
      parts: [{ type: "text" as const, text: m.content }],
    }));

    chat.messages = messages;
  } catch {
    // History is optional — don't block the chat if it fails
  }
}
