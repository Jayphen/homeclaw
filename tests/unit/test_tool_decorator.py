"""Tests for the tool_decorator module — auto-generating schemas from signatures."""

from typing import Annotated, Any, Literal

from homeclaw.agent.tool_decorator import Desc, Enum, ToolRegistration, tool


class TestBasicTypeMapping:
    def test_str_param(self) -> None:
        @tool(name="t", description="d")
        async def fn(*, name: str, **_: Any) -> dict[str, Any]:
            return {}

        defn = fn  # type: ignore[assignment]
        # The decorator returns the original function, but we use the
        # ToolRegistration to build the definition.
        # Actually, we need the ToolRegistration object.
        reg = tool(name="t", description="d")
        async def fn2(*, name: str, **_: Any) -> dict[str, Any]:
            return {}
        reg(fn2)
        d = reg.definition()
        assert d.parameters["properties"]["name"] == {"type": "string"}
        assert d.parameters["required"] == ["name"]

    def test_int_param(self) -> None:
        reg = tool(name="t", description="d")
        async def fn(*, count: int, **_: Any) -> dict[str, Any]:
            return {}
        reg(fn)
        d = reg.definition()
        assert d.parameters["properties"]["count"] == {"type": "integer"}

    def test_bool_param(self) -> None:
        reg = tool(name="t", description="d")
        async def fn(*, flag: bool, **_: Any) -> dict[str, Any]:
            return {}
        reg(fn)
        d = reg.definition()
        assert d.parameters["properties"]["flag"] == {"type": "boolean"}

    def test_list_str_param(self) -> None:
        reg = tool(name="t", description="d")
        async def fn(*, tags: list[str], **_: Any) -> dict[str, Any]:
            return {}
        reg(fn)
        d = reg.definition()
        assert d.parameters["properties"]["tags"] == {
            "type": "array",
            "items": {"type": "string"},
        }


class TestOptionalParams:
    def test_optional_via_union_none(self) -> None:
        reg = tool(name="t", description="d")
        async def fn(*, name: str, topic: str | None = None, **_: Any) -> dict[str, Any]:
            return {}
        reg(fn)
        d = reg.definition()
        assert d.parameters["required"] == ["name"]
        assert "topic" in d.parameters["properties"]

    def test_optional_via_default(self) -> None:
        reg = tool(name="t", description="d")
        async def fn(*, name: str, scope: str = "household", **_: Any) -> dict[str, Any]:
            return {}
        reg(fn)
        d = reg.definition()
        assert d.parameters["required"] == ["name"]


class TestLiteralAndEnum:
    def test_literal_type(self) -> None:
        reg = tool(name="t", description="d")
        async def fn(*, scope: Literal["household", "private"], **_: Any) -> dict[str, Any]:
            return {}
        reg(fn)
        d = reg.definition()
        prop = d.parameters["properties"]["scope"]
        assert prop["enum"] == ["household", "private"]
        assert prop["type"] == "string"

    def test_enum_annotation(self) -> None:
        reg = tool(name="t", description="d")
        async def fn(
            *, scope: Annotated[str, Enum(["household", "private"])], **_: Any
        ) -> dict[str, Any]:
            return {}
        reg(fn)
        d = reg.definition()
        prop = d.parameters["properties"]["scope"]
        assert prop["enum"] == ["household", "private"]


class TestDescAnnotation:
    def test_desc_in_schema(self) -> None:
        reg = tool(name="t", description="d")
        async def fn(
            *, id: Annotated[str, Desc("Contact ID")], **_: Any
        ) -> dict[str, Any]:
            return {}
        reg(fn)
        d = reg.definition()
        assert d.parameters["properties"]["id"]["description"] == "Contact ID"

    def test_desc_and_enum_combined(self) -> None:
        reg = tool(name="t", description="d")
        async def fn(
            *,
            scope: Annotated[str, Desc("Target scope"), Enum(["household", "private"])],
            **_: Any,
        ) -> dict[str, Any]:
            return {}
        reg(fn)
        d = reg.definition()
        prop = d.parameters["properties"]["scope"]
        assert prop["description"] == "Target scope"
        assert prop["enum"] == ["household", "private"]


class TestSchemaOverrides:
    def test_override_replaces_auto_schema(self) -> None:
        reg = tool(
            name="t",
            description="d",
            schema_overrides={
                "files": {
                    "type": "array",
                    "description": "Files to create",
                    "items": {
                        "type": "object",
                        "properties": {
                            "filename": {"type": "string"},
                            "content": {"type": "string"},
                        },
                        "required": ["filename", "content"],
                    },
                },
            },
        )
        async def fn(
            *, name: str, files: list[dict[str, Any]] | None = None, **_: Any
        ) -> dict[str, Any]:
            return {}
        reg(fn)
        d = reg.definition()
        assert d.parameters["properties"]["files"]["items"]["required"] == [
            "filename", "content",
        ]
        assert d.parameters["required"] == ["name"]


class TestNoParams:
    def test_empty_properties(self) -> None:
        reg = tool(name="t", description="d")
        async def fn(**_: Any) -> dict[str, Any]:
            return {}
        reg(fn)
        d = reg.definition()
        assert d.parameters["properties"] == {}
        assert "required" not in d.parameters


class TestRegistration:
    def test_register_on_registry(self) -> None:
        from homeclaw.agent.tools import ToolRegistry

        registry = ToolRegistry()
        reg = tool(name="my_tool", description="A test tool")
        async def fn(*, name: str, **_: Any) -> dict[str, Any]:
            return {"ok": True}
        reg(fn)
        reg.register(registry)

        assert registry.has_tool("my_tool")
        defn = [d for d in registry.get_definitions() if d.name == "my_tool"][0]
        assert defn.description == "A test tool"
        assert defn.parameters["required"] == ["name"]

    def test_definition_metadata(self) -> None:
        reg = tool(name="contact_get", description="Get a contact by ID.")
        async def fn(*, id: str, **_: Any) -> dict[str, Any]:
            return {}
        reg(fn)
        d = reg.definition()
        assert d.name == "contact_get"
        assert d.description == "Get a contact by ID."


class TestKwargsIgnored:
    def test_var_keyword_not_in_schema(self) -> None:
        reg = tool(name="t", description="d")
        async def fn(*, name: str, **_: Any) -> dict[str, Any]:
            return {}
        reg(fn)
        d = reg.definition()
        assert "_" not in d.parameters["properties"]
        assert list(d.parameters["properties"].keys()) == ["name"]
