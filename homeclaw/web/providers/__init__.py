"""Built-in web providers — auto-registered on import."""

from homeclaw.web.providers.jina import JinaProvider
from homeclaw.web.providers.tavily import TavilyProvider

__all__ = ["JinaProvider", "TavilyProvider", "register_builtins"]


def register_builtins(
    *,
    jina_api_key: str | None = None,
    tavily_api_key: str | None = None,
) -> None:
    """Register built-in providers with the global registry."""
    from homeclaw.web.protocol import BuiltinProvider
    from homeclaw.web.registry import web_providers

    jina = JinaProvider(api_key=jina_api_key)
    web_providers.register(
        BuiltinProvider.JINA, search=jina, read=jina,
    )

    tavily = TavilyProvider(api_key=tavily_api_key)
    web_providers.register(
        BuiltinProvider.TAVILY, search=tavily, read=tavily,
    )
