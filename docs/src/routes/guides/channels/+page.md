<svelte:head>
  <title>Channels — homeclaw docs</title>
</svelte:head>

# Channels

Channel adapters bridge messaging platforms to the homeclaw agent loop. Each adapter handles platform-specific concerns (auth, message formats, media) and presents a uniform interface to the agent.

## Telegram

Uses `python-telegram-bot`. Requires `TELEGRAM_TOKEN`.

Features:
- Text messages and photo handling
- Group chat support
- Typing indicators during processing
- `/register <name>` to link a Telegram account to a household member
- `/start` welcome message

### Setup

1. Create a bot via [@BotFather](https://t.me/botfather)
2. Add the token in the web UI under Settings > Telegram, or set `TELEGRAM_TOKEN`
3. Optionally restrict access with `TELEGRAM_ALLOWED_USERS` (comma-separated user IDs)

## WhatsApp

Uses [neonize](https://github.com/krypton-byte/neonize) (Python bindings for whatsmeow). Connects as a linked device via QR code or pair code — **no Meta Business API required**.

Features:
- Text messages and photo handling
- Group chat support
- `/register <name>` for account linking

### Setup

1. Enable WhatsApp in the web UI under Settings
2. Scan the QR code at Settings > WhatsApp (also available at `GET /api/setup/whatsapp/qr`)
3. Optionally set `whatsapp_allowed_users` (comma-separated phone numbers)

Install the WhatsApp extra:

```bash
pip install homeclaw[whatsapp]
```

Auth is stored in `workspaces/household/whatsapp.db`.

## REPL

Terminal chat for development. No external dependencies.

```bash
homeclaw chat --person alice
```

## Web UI

The web UI provides a chat interface at `http://localhost:8080`. Auth is handled via per-member JWT sessions.

## Channel dispatcher

The channel dispatcher routes outbound messages (from `message_send` tool and scheduler) to each person's preferred channel. Per-person channel preferences are stored in `workspaces/household/channel_preferences.json`.

Preferences are auto-set when a person runs `/register` on a channel, and can be changed via the `channel_preference_set` tool.
