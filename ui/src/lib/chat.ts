import { Chat, type UIMessage } from "@ai-sdk/svelte";
import { TextStreamChatTransport } from "ai";
import { api, getToken } from "$lib/api";

export type ChatTab = "private" | "household";

function createChat(channel?: string): Chat {
  return new Chat({
    transport: new TextStreamChatTransport({
      api: "/api/chat",
      headers: () => {
        const token = getToken();
        return token ? { Authorization: `Bearer ${token}` } : {};
      },
      prepareSendMessagesRequest: ({ messages, headers, credentials, api: url }) => ({
        body: {
          messages: messages.slice(-1),
          ...(channel ? { channel } : {}),
        },
        headers,
        credentials,
        api: url,
      }),
    }),
  });
}

/** Private (DM) chat — no channel, full personal context. */
export const privateChat = createChat();

/** Household chat — shared context, channel-scoped history. */
export const householdChat = createChat("web-household");

const historyLoaded = { private: false, household: false };

/** In-flight promises to prevent concurrent history requests per tab. */
const historyPromises: Partial<Record<ChatTab, Promise<void>>> = {};

/** Load recent conversation history for a given tab (once per tab). */
export function loadHistory(tab: ChatTab = "private"): Promise<void> {
  const instance = tab === "household" ? householdChat : privateChat;
  if (historyLoaded[tab] || instance.messages.length > 0)
    return Promise.resolve();

  // Return existing in-flight request to avoid duplicates on rapid tab switches
  if (historyPromises[tab]) return historyPromises[tab];

  const promise = (async () => {
    try {
      const url =
        tab === "household"
          ? "/api/chat/history?channel=web-household"
          : "/api/chat/history";
      const resp = await api(url);
      if (!resp.ok) return;
      const data: { role: string; content: string }[] = await resp.json();
      if (!data.length) return;

      let counter = 0;
      const messages: UIMessage[] = data.map((m) => ({
        id: `hist-${tab}-${counter++}`,
        role: m.role as "user" | "assistant",
        parts: [{ type: "text" as const, text: m.content }],
      }));

      instance.messages = messages;
      historyLoaded[tab] = true;
    } catch {
      // History is optional — don't block the chat if it fails
    } finally {
      delete historyPromises[tab];
    }
  })();

  historyPromises[tab] = promise;
  return promise;
}

// Keep the old exports for backwards compat with any other consumers
export const chat = privateChat;
