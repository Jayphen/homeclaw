"""Memory API routes — serves markdown-based memory topics."""

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Query

from homeclaw import HOUSEHOLD_WORKSPACE
from homeclaw.api.deps import (
    MemberDep,
    get_config,
    list_member_workspaces,
    require_person_access,
    validate_person,
    visible_members,
)
from homeclaw.memory.markdown import memory_list_topics, memory_read_topic, memory_save_topic
from homeclaw.memory.semantic import SemanticMemory
from homeclaw.memory.status import get_semantic_status

router = APIRouter(prefix="/api/memory", tags=["memory"])


@router.get("")
async def memory_list(
    member: Annotated[str | None, MemberDep],
) -> dict[str, Any]:
    config = get_config()
    workspaces = config.workspaces.resolve()
    all_members = list_member_workspaces(workspaces)
    members = visible_members(member, all_members)
    # Always include household — it's visible to all members
    if HOUSEHOLD_WORKSPACE not in members:
        members = [*members, HOUSEHOLD_WORKSPACE]
    result: list[dict[str, Any]] = []
    for person in members:
        topics = memory_list_topics(workspaces, person)
        # Get last modified time across all topic files
        memory_dir = workspaces / person / "memory"
        last_updated: datetime | None = None
        if memory_dir.is_dir():
            for f in memory_dir.iterdir():
                if f.suffix == ".md":
                    mtime = datetime.fromtimestamp(f.stat().st_mtime)
                    if last_updated is None or mtime > last_updated:
                        last_updated = mtime
        result.append({
            "person": person,
            "topic_count": len(topics),
            "topics": topics,
            "last_updated": last_updated.isoformat() if last_updated else None,
        })
    return {
        "members": result,
        "semantic_ready": get_semantic_status(workspaces) == "ready",
    }


@router.get("/{person}")
async def memory_detail(
    person: str,
    member: Annotated[str | None, MemberDep],
) -> dict[str, Any]:
    workspaces = get_config().workspaces.resolve()
    validate_person(person, workspaces)
    require_person_access(member, person)
    topics = memory_list_topics(workspaces, person)
    topic_contents: dict[str, str] = {}
    for topic in topics:
        content = memory_read_topic(workspaces, person, topic)
        if content is not None:
            topic_contents[topic] = content
    return {"person": person, "topics": topic_contents}


@router.post("/{person}/{topic}")
async def memory_append(
    person: str,
    topic: str,
    body: dict[str, str],
    member: Annotated[str | None, MemberDep],
) -> dict[str, Any]:
    """Append an entry to a memory topic."""
    workspaces = get_config().workspaces.resolve()
    validate_person(person, workspaces)
    require_person_access(member, person)
    content = body.get("content", "").strip()
    if not content:
        return {"error": "content is required"}
    memory_save_topic(workspaces, person, topic, content)
    return {"status": "saved", "person": person, "topic": topic}


@router.get("/{person}/recall")
async def memory_recall(
    person: str,
    member: Annotated[str | None, MemberDep],
    q: str = Query(..., description="Search query"),
    top_k: int = Query(default=5, ge=1, le=20),
) -> dict[str, Any]:
    config = get_config()
    workspaces = config.workspaces.resolve()
    validate_person(person, workspaces)
    require_person_access(member, person)
    embedding_provider = "openai" if config.openai_api_key else "local"
    semantic = SemanticMemory(
        str(workspaces),
        embedding_provider=embedding_provider,
        embedding_api_key=config.openai_api_key,
    )
    await semantic.initialize()
    if not semantic.enabled:
        return {"person": person, "query": q, "results": [], "note": "Semantic memory not enabled"}
    results = await semantic.recall(q, top_k=top_k, person=person)
    return {"person": person, "query": q, "results": results}
