"""Entity and Alias API routes."""
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel

from src.core.filesystem import FilesystemService
from src.core.alias_manager import AliasManager
from src.dependencies import get_filesystem

router = APIRouter()


class EntityAliasResponse(BaseModel):
    """Entity alias response model."""
    canonical_name: str
    aliases: List[str]
    entity_type: str
    disambiguation_note: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class EntityAliasCreateRequest(BaseModel):
    """Create entity alias request."""
    canonical_name: str
    alias: str
    entity_type: str
    disambiguation_note: Optional[str] = None


class EntityAliasMergeRequest(BaseModel):
    """Merge entities request."""
    keep_name: str
    merge_name: str


class EntityResolveRequest(BaseModel):
    """Resolve entity name request."""
    name: str


class EntityResolveResponse(BaseModel):
    """Resolve entity name response."""
    name: str
    canonical_name: Optional[str] = None
    found: bool


class EntitySearchResponse(BaseModel):
    """Entity search response."""
    query: str
    results: List[EntityAliasResponse]


def get_alias_manager(fs: FilesystemService = Depends(get_filesystem)) -> AliasManager:
    """Get alias manager dependency."""
    return AliasManager(fs)


@router.get("/entities", response_model=List[EntityAliasResponse])
async def list_entities(
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    alias_manager: AliasManager = Depends(get_alias_manager),
):
    """List all entities and their aliases."""
    entities = alias_manager.get_all_entities()
    
    results = []
    for canonical, entity in entities.items():
        if entity_type and entity.entity_type != entity_type:
            continue
        results.append(EntityAliasResponse(
            canonical_name=entity.canonical_name,
            aliases=entity.aliases,
            entity_type=entity.entity_type,
            disambiguation_note=entity.disambiguation_note,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        ))
    
    return results


@router.get("/entities/{canonical_name}", response_model=EntityAliasResponse)
async def get_entity(
    canonical_name: str,
    alias_manager: AliasManager = Depends(get_alias_manager),
):
    """Get a specific entity by canonical name."""
    entity = alias_manager.get_entity(canonical_name)
    if not entity:
        raise HTTPException(status_code=404, detail=f"Entity '{canonical_name}' not found")
    
    return EntityAliasResponse(
        canonical_name=entity.canonical_name,
        aliases=entity.aliases,
        entity_type=entity.entity_type,
        disambiguation_note=entity.disambiguation_note,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


@router.post("/entities", response_model=EntityAliasResponse)
async def create_entity_alias(
    request: EntityAliasCreateRequest,
    alias_manager: AliasManager = Depends(get_alias_manager),
):
    """Create a new entity or add an alias to an existing entity."""
    alias_manager.add_alias(
        canonical_name=request.canonical_name,
        alias=request.alias,
        entity_type=request.entity_type,
        disambiguation_note=request.disambiguation_note,
    )
    
    entity = alias_manager.get_entity(request.canonical_name)
    return EntityAliasResponse(
        canonical_name=entity.canonical_name,
        aliases=entity.aliases,
        entity_type=entity.entity_type,
        disambiguation_note=entity.disambiguation_note,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


@router.post("/entities/resolve", response_model=EntityResolveResponse)
async def resolve_entity_name(
    request: EntityResolveRequest,
    alias_manager: AliasManager = Depends(get_alias_manager),
):
    """Resolve an entity name to its canonical form."""
    canonical = alias_manager.resolve_name(request.name)
    
    return EntityResolveResponse(
        name=request.name,
        canonical_name=canonical,
        found=canonical is not None,
    )


@router.get("/entities/search", response_model=EntitySearchResponse)
async def search_entities(
    query: str = Query(..., description="Search query"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    alias_manager: AliasManager = Depends(get_alias_manager),
):
    """Search for entities by name or alias."""
    results = alias_manager.search_entities(query, entity_type)
    
    return EntitySearchResponse(
        query=query,
        results=[
            EntityAliasResponse(
                canonical_name=e.canonical_name,
                aliases=e.aliases,
                entity_type=e.entity_type,
                disambiguation_note=e.disambiguation_note,
                created_at=e.created_at,
                updated_at=e.updated_at,
            )
            for e in results
        ],
    )


@router.post("/entities/merge")
async def merge_entities(
    request: EntityAliasMergeRequest,
    alias_manager: AliasManager = Depends(get_alias_manager),
):
    """Merge two entities together."""
    try:
        alias_manager.merge_entities(request.keep_name, request.merge_name)
        return {
            "success": True,
            "message": f"Merged '{request.merge_name}' into '{request.keep_name}'",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/entities/{canonical_name}/aliases/{alias}")
async def remove_alias(
    canonical_name: str,
    alias: str,
    alias_manager: AliasManager = Depends(get_alias_manager),
):
    """Remove an alias from an entity."""
    alias_manager.remove_alias(canonical_name, alias)
    return {"success": True, "message": f"Removed alias '{alias}' from '{canonical_name}'"}


@router.get("/entities/{canonical_name}/suggestions")
async def suggest_aliases(
    canonical_name: str,
    entity_type: str = Query(..., description="Entity type for context"),
    alias_manager: AliasManager = Depends(get_alias_manager),
):
    """Get suggested aliases for an entity."""
    suggestions = alias_manager.suggest_aliases(canonical_name, entity_type)
    return {
        "canonical_name": canonical_name,
        "entity_type": entity_type,
        "suggestions": suggestions,
    }
