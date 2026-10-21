from fastapi import APIRouter, Depends
from app.core.deps import require_api_key
from app.services.search_service import SearchService

router = APIRouter(tags=["misc"])
svc = SearchService()

@router.get("/stats", dependencies=[Depends(require_api_key)])
async def stats():
    return await svc.stats()

@router.get("/sources", dependencies=[Depends(require_api_key)])
async def sources():
    return await svc.sources()
