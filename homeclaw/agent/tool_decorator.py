"""Auto-generate ToolDefinition schemas from type-annotated function signatures.

Usage:
    @tool(
        name="contact_get",
        description="Get full details for a contact by ID.",
    )
    async def contact_get(*, id: str, **_: Any) -> dict[str, Any]:
        ...

The decorator inspects the function signature and type hints to build
the JSON schema automatically. Supported types:

    str, int, bool               → "string", "integer", "boolean"
    list[str]                    → {"type": "array", "items": {"type": "string"}}
    str | None, Optional[str]   → "string" (parameter becomes optional)
    Literal["a", "b"]           → {"type": "string", "enum": ["a", "b"]}

Parameters with defaults are optional; without defaults are required.
The ``**_: Any`` catch-all is ignored.

For parameter descriptions or enum overrides, use ``Annotated``:

    from typing import Annotated
    from homeclaw.agent.tool_decorator import Desc, Enum

    async def my_tool(
        *,
        id: Annotated[str, Desc("Contact ID")],
        scope: Annotated[str, Enum(["household", "private"]), Desc("Scope")],
    ) -> dict[str, Any]: ...

For complex nested schemas that can't be expressed via type hints,
pass ``schema_overrides`` to override specific parameter schemas:

    @tool(
        name="skill_create",
        description="...",
        schema_overrides={
            "initial_files": {
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
"""

import inspect
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, Union, get_args, get_origin

from homeclaw.agent.providers.base import ToolDefinition

if TYPE_CHECKING:
    from homeclaw.agent.tools import ToolRegistry

ToolHandler = Callable[..., Coroutine[Any, Any, dict[str, Any]]]

# --- Annotation markers ---


@dataclass(frozen=True, slots=True)
class Desc:
    """Parameter description annotation."""
    text: str


@dataclass(frozen=True, slots=True)
class Enum:
    """Explicit enum values annotation."""
    values: list[str]


# --- Type mapping ---

_PYTHON_TO_JSON: dict[type, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
}


def _literal_enum_values(annotation: Any) -> list[Any] | None:
    """Extract enum values from a Literal type or type alias to Literal.

    Returns the list of values if the annotation is Literal[...], else None.
    """
    origin = get_origin(annotation)
    args = get_args(annotation)
    if origin is Literal and args:
        return list(args)
    return None


def _type_to_schema(annotation: Any) -> tuple[dict[str, Any], bool]:
    """Convert a type annotation to a JSON schema fragment.

    Returns (schema_dict, is_optional).
    """
    origin = get_origin(annotation)
    args = get_args(annotation)

    # Union types: X | None or Optional[X]
    if origin is Union:
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1:
            schema, _ = _type_to_schema(non_none[0])
            return schema, True
        # Multi-type union without None — fall back to string
        return {"type": "string"}, False

    # Literal["a", "b", "c"] — also catches type aliases like SkillScope
    values = _literal_enum_values(annotation)
    if values is not None:
        if values and isinstance(values[0], str):
            return {"type": "string", "enum": values}, False
        if values and isinstance(values[0], int):
            return {"type": "integer", "enum": values}, False
        return {"type": "string", "enum": [str(v) for v in values]}, False

    # list[X]
    if origin is list:
        if args:
            item_schema, _ = _type_to_schema(args[0])
            return {"type": "array", "items": item_schema}, False
        return {"type": "array"}, False

    # dict[str, Any] — generic object
    if origin is dict:
        return {"type": "object"}, False

    # Simple scalar types
    if annotation in _PYTHON_TO_JSON:
        return {"type": _PYTHON_TO_JSON[annotation]}, False

    # Enum types (e.g. InteractionType = Literal[...])
    # Check if annotation is itself a type alias for Literal
    alias_origin = get_origin(annotation)
    alias_args = get_args(annotation)
    if alias_origin is Literal and alias_args:
        return {"type": "string", "enum": list(alias_args)}, False

    # Fallback
    return {"type": "string"}, False


def _extract_annotations(annotation: Any) -> tuple[Any, str | None, list[str] | None]:
    """Extract the base type, Desc, and Enum from an Annotated type.

    Returns (base_type, description, enum_values).
    """
    origin = get_origin(annotation)
    if origin is not None:
        # Check for typing.Annotated
        try:
            from typing import Annotated
            if origin is Annotated:
                args = get_args(annotation)
                base = args[0]
                desc = None
                enum_vals = None
                for meta in args[1:]:
                    if isinstance(meta, Desc):
                        desc = meta.text
                    elif isinstance(meta, Enum):
                        enum_vals = meta.values
                return base, desc, enum_vals
        except ImportError:
            pass
    return annotation, None, None


def _build_schema(
    func: ToolHandler,
    schema_overrides: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a JSON schema from a function's signature and type hints."""
    sig = inspect.signature(func)
    hints = func.__annotations__  # includes return type if present

    properties: dict[str, dict[str, Any]] = {}
    required: list[str] = []

    for name, param in sig.parameters.items():
        # Skip **kwargs catch-all
        if param.kind == inspect.Parameter.VAR_KEYWORD:
            continue
        # Skip *args
        if param.kind == inspect.Parameter.VAR_POSITIONAL:
            continue

        # Use override if provided
        if schema_overrides and name in schema_overrides:
            properties[name] = schema_overrides[name]
            if param.default is inspect.Parameter.empty:
                required.append(name)
            continue

        raw_hint = hints.get(name, str)
        base_type, desc, enum_vals = _extract_annotations(raw_hint)
        schema, is_optional = _type_to_schema(base_type)

        # Apply explicit Enum override; if absent, auto-extract from Literal
        if enum_vals is None:
            enum_vals_auto = _literal_enum_values(base_type)
            if enum_vals_auto is not None and "enum" not in schema:
                schema["enum"] = enum_vals_auto
        if enum_vals is not None:
            schema["enum"] = enum_vals

        # Apply description
        if desc is not None:
            schema["description"] = desc

        properties[name] = schema

        # Determine required: no default and not optional type
        has_default = param.default is not inspect.Parameter.empty
        if not has_default and not is_optional:
            required.append(name)

    result: dict[str, Any] = {
        "type": "object",
        "properties": properties,
    }
    if required:
        result["required"] = required
    return result


def tool(
    name: str,
    description: str,
    *,
    schema_overrides: dict[str, dict[str, Any]] | None = None,
) -> "ToolRegistration":
    """Decorator that marks a function as a tool with auto-generated schema.

    Returns a ToolRegistration that can be registered with a ToolRegistry.
    """
    return ToolRegistration(name, description, schema_overrides)


class ToolRegistration:
    """Intermediate object from the @tool decorator — call .register() to wire up."""

    def __init__(
        self,
        name: str,
        description: str,
        schema_overrides: dict[str, dict[str, Any]] | None,
    ) -> None:
        self._name = name
        self._description = description
        self._schema_overrides = schema_overrides
        self._func: ToolHandler | None = None

    def __call__(self, func: ToolHandler) -> ToolHandler:
        self._func = func
        return func

    def definition(self) -> ToolDefinition:
        """Build the ToolDefinition from the decorated function."""
        assert self._func is not None, "Decorator not applied to a function"
        return ToolDefinition(
            name=self._name,
            description=self._description,
            parameters=_build_schema(self._func, self._schema_overrides),
        )

    @property
    def handler(self) -> ToolHandler:
        assert self._func is not None, "Decorator not applied to a function"
        return self._func

    def register(self, registry: "ToolRegistry") -> None:
        """Register this tool with the given registry."""
        registry.register(self.definition(), self.handler)
