<svelte:head>
  <title>Adding Tools — homeclaw docs</title>
</svelte:head>

# Adding Tools

## Steps

1. Define a handler function in `homeclaw/agent/tools/`
2. Create a `ToolDefinition` with name, description, parameters schema, and handler reference
3. Register it in the tool registry
4. Write a test in `tests/unit/test_tools/`

Run `make typecheck` to confirm the handler signature satisfies the expected protocol.

## Schema rules

Tool schemas in `homeclaw/agent/tools.py` must mirror the Pydantic models they wrap. When you add or change a `Literal`, enum, or field on a model, update the corresponding tool schema `enum`/`properties` to match.

## Personal write tools

If your new tool writes to `workspaces/{person}/`, add it to `_PERSONAL_WRITE_TOOLS` in `homeclaw/agent/loop.py`. This ensures the `person` argument is forced to the authenticated caller in DMs, preventing cross-person writes.

Read-only tools and cross-person tools like `message_send` are intentionally excluded from this enforcement.

## Adding a plugin

1. Implement the `Plugin` protocol defined in `homeclaw/plugins/interface.py`
2. Place your module at `workspaces/plugins/{name}/plugin.py`
3. The plugin registry discovers it via importlib at startup
4. Write a test — plugins are loaded in isolation so unit testing is straightforward

See `plugins/plants/` for a reference implementation.
