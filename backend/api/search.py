from fastapi import APIRouter, HTTPException, Query

from backend.services import search_service

router = APIRouter()


@router.get("/search")
async def search(q: str = Query("")) -> dict:
    q = q.strip()
    if not q:
        return {"query": q, "results": []}
    try:
        results = await search_service.search(q)
    except Exception as exc:
        raise HTTPException(500, str(exc)) from exc
    return {"query": q, "results": results}
