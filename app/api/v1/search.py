from typing import Optional, List
from fastapi import APIRouter, Query, Request, BackgroundTasks, Depends
from app.core.deps import require_api_key
from app.models.schemas import MembreRecord
from app.services.search_service import SearchService
from app.repositories import usage_repo
from app.integrations.telegram import notify_search

router = APIRouter(tags=["search"])
svc = SearchService()

@router.get("/search", response_model=List[MembreRecord])
async def search(
    request: Request,
    background: BackgroundTasks,
    q: Optional[str] = None,
    nom: Optional[str] = None,
    prenom: Optional[str] = None,
    date_naissance: Optional[str] = None,
    jour: Optional[str] = None,
    mois: Optional[str] = None,
    annee: Optional[str] = None,
    code_postal: Optional[str] = None,
    ville: Optional[str] = None,
    tel: Optional[str] = None,
    mail: Optional[str] = None,
    source: Optional[str] = None,
    limit: int = Query(100, ge=1, le=5000),
    auth: dict = Depends(require_api_key),
):
    filters = dict(q=q, nom=nom, prenom=prenom, date_naissance=date_naissance,
                   jour=jour, mois=mois, annee=annee, code_postal=code_postal,
                   ville=ville, tel=tel, mail=mail, source=source)
    results = await svc.search(limit=limit, **filters)
    criteria = svc.criteria_from(filters)
    request.state.audit_meta = {"nb_results": len(results), "criteria": criteria}
    if criteria:
        ip = (request.headers.get("x-forwarded-for", "").split(",")[0].strip()
              or (request.client.host if request.client else "?"))
        background.add_task(notify_search, ip, criteria)
        background.add_task(usage_repo.log_search,
                            ip, getattr(request.state, "key_id", ""), criteria, len(results))
    return results
