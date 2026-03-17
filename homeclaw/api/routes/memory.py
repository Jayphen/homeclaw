"""Memory API routes."""

from typing import Any

from fastapi import APIRouter, Query

from homeclaw.api.deps import AuthDep, get_config, list_member_workspaces
from homeclaw.memory.facts import HouseholdMemory, load_memory, save_memory
from homeclaw.memory.semantic import SemanticMemory

router = APIRouter(prefix="/api/memory", tags=["memory"])


@router.get("", dependencies=[AuthDep])
async def memory_list() -> dict[str, Any]:
    config = get_config()
    workspaces = config.workspaces.resolve()
    members = list_member_workspaces(workspaces)
    result: list[dict[str, Any]] = []
    for person in members:
        mem = load_memory(workspaces, person)
        result.append({
            "person": person,
            "fact_count": len(mem.facts),
            "preference_count": len(mem.preferences),
            "last_updated": mem.last_updated.isoformat() if mem.last_updated else None,
        })
    semantic = SemanticMemory(str(workspaces))
    await semantic.initialize()
    return {
        "members": result,
        "semantic_ready": config.enhanced_memory and semantic.enabled,
    }


@router.get("/{person}", dependencies=[AuthDep])
async def memory_detail(person: str) -> dict[str, Any]:
    workspaces = get_config().workspaces.resolve()
    mem = load_memory(workspaces, person)
    return {
        "person": person,
        **mem.model_dump(mode="json"),
    }


@router.put("/{person}/facts", dependencies=[AuthDep])
async def memory_update_facts(person: str, body: HouseholdMemory) -> dict[str, Any]:
    workspaces = get_config().workspaces.resolve()
    mem = load_memory(workspaces, person)
    mem.facts = body.facts
    if body.preferences:
        mem.preferences = body.preferences
    save_memory(workspaces, person, mem)
    return {"status": "updated", "person": person}


@router.get("/{person}/recall", dependencies=[AuthDep])
async def memory_recall(
    person: str,
    q: str = Query(..., description="Search query"),
    top_k: int = Query(default=5, ge=1, le=20),
) -> dict[str, Any]:
    workspaces = get_config().workspaces.resolve()
    semantic = SemanticMemory(str(workspaces))
    await semantic.initialize()
    if not semantic.enabled:
        return {"person": person, "query": q, "results": [], "note": "Semantic memory not enabled"}
    results = await semantic.recall(q, top_k=top_k)
    return {"person": person, "query": q, "results": results}
