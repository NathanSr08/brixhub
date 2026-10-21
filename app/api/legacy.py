from app.integrations.telegram import notify_search
import hmac
import hashlib
from fastapi import BackgroundTasks, APIRouter, Request, HTTPException, Response
from app.core.config import get_settings
from app.services.search_service import SearchService
from app.services.correlation_service import CorrelationService
from app.repositories import membres_repo

router = APIRouter(prefix="/api", tags=["legacy-web"])
search_svc = SearchService()
corr_svc = CorrelationService()

def _get_web_signature(secret: str) -> str:
    return hmac.new(secret.encode(), b"brixhub_internal_web_session", hashlib.sha256).hexdigest()

def verify_web_session(request: Request):
    s = get_settings()
    expected = _get_web_signature(s.admin_token)
    token = request.cookies.get("bx_web_session")
    if not token or not hmac.compare_digest(token, expected):
        raise HTTPException(status_code=403, detail="Accès non autorisé (Session Web requise)")

@router.get("/sources")
async def get_sources():
    return membres_repo.list_sources()

@router.get("/stats")
async def get_stats():
    total = membres_repo.total_rows()
    by_source = membres_repo.count_by_source()
    return {"total": total, "by_source": by_source}

@router.get("/search")
async def web_search(
    request: Request,
    background: BackgroundTasks,
    q: str | None = None,
    nom: str | None = None,
    prenom: str | None = None,
    date_naissance: str | None = None,
    jour: str | None = None,
    mois: str | None = None,
    annee: str | None = None,
    code_postal: str | None = None,
    ville: str | None = None,
    tel: str | None = None,
    mail: str | None = None,
    source: str | None = None,
    limit: int = 50,
):
    verify_web_session(request)
    results = await search_svc.search(
        q=q, nom=nom, prenom=prenom, date_naissance=date_naissance,
        jour=jour, mois=mois, annee=annee, code_postal=code_postal,
        ville=ville, tel=tel, mail=mail, source=source, limit=limit
    )
    criteria = {
        k: v for k, v in {
            "q": q, "nom": nom, "prenom": prenom, "date_naissance": date_naissance,
            "jour": jour, "mois": mois, "annee": annee, "code_postal": code_postal,
            "ville": ville, "tel": tel, "mail": mail, "source": source
        }.items() if v
    }
    if criteria:
        ip = (request.headers.get("x-forwarded-for", "").split(",")[0].strip()
              or (request.client.host if request.client else "?"))
        background.add_task(notify_search, ip, criteria)
    return results

@router.get("/correlations")
async def web_correlations(
    request: Request,
    nom: str = "",
    prenom: str = "",
    date_naissance: str = "",
    tel: str = "",
    mail: str = "",
    code_postal: str = "",
    adresse: str = "",
    source: str = ""
):
    verify_web_session(request)
    return await corr_svc.get_correlations(
        nom=nom, prenom=prenom, date_naissance=date_naissance,
        tel=tel, mail=mail, code_postal=code_postal,
        adresse=adresse, source=source
    )
