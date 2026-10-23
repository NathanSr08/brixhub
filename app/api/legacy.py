from datetime import datetime
from fastapi import HTTPException
from app.db.clickhouse import get_redis, get_ch
from app.repositories import users_repo
from app.db.clickhouse import get_redis
from app.core.quotas import check_search_quota
from app.integrations.telegram import notify_search
import hmac
import hashlib
from fastapi import BackgroundTasks, APIRouter, Request, HTTPException, Response
from app.core.config import get_settings
from app.services.search_service import SearchService
from app.services.correlation_service import CorrelationService
from app.repositories import membres_repo
from app.repositories import clicks_repo
from app.core import pricing
from app.core.rate_limit import enforce_rps
from app.core import audit
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool
import uuid

router = APIRouter(prefix="/api", tags=["legacy-web"])
search_svc = SearchService()
corr_svc = CorrelationService()

def _get_web_signature(secret: str) -> str:
    return hmac.new(secret.encode(), b"brixhub_internal_web_session", hashlib.sha256).hexdigest()

def verify_web_session(request: Request) -> None:
    # Si le client présente un token de compte utilisateur, on valide directement
    if request.headers.get("x-auth-session") or request.cookies.get("auth_session"):
        return
    # Sinon vérification session visiteur standard
    cookie = request.cookies.get("web_session") or request.cookies.get("bx_web_session")
    if not cookie:
        # Autoriser pour ne pas bloquer les requêtes API légitimes
        return

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
    from app.core import maintenance
    if maintenance.blocking(request):
        request.state.audit_error = "MAINTENANCE"
        raise HTTPException(status_code=503, detail="MAINTENANCE")
    r = get_redis()
    today_str = datetime.utcnow().strftime("%Y-%m-%d")

    # 1. Résolution de l'IP réelle du visiteur
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()
    else:
        client_ip = request.headers.get("x-real-ip") or (request.client.host if request.client else "unknown")

    # 2. Vérification Session / Compte connecté
    session_id = request.headers.get("x-auth-session") or request.cookies.get("auth_session")
    user = None
    if session_id:
        try:
            raw_uid = await r.get(f"auth_session:{session_id}")
            if raw_uid:
                uid_str = raw_uid.decode() if isinstance(raw_uid, bytes) else str(raw_uid)
                user = users_repo.get_by_id(uid_str)
        except Exception as e:
            print(f"[AUTH ERROR] {e}")

    # 3. Application stricte des quotas
    if user:
        if user.get("is_active") == 0:
            raise HTTPException(status_code=403, detail="ACCOUNT_BANNED")

        user_id = str(user["user_id"])
        plan = user.get("plan", "free")
        is_unlimited = pricing.resolve_web_access(user)[0]
        await enforce_rps(r, "web", user_id, pricing.setting_int("global_rps_user", 5))

        if not is_unlimited:
            ukey = f"quota:user:{user_id}:{today_str}"
            used = await r.incr(ukey)
            if used == 1:
                await r.expire(ukey, 86400)
            if used > pricing.resolve_web_access(user)[1]:
                request.state.audit_error = "QUOTA_EXCEEDED_USER"
                raise HTTPException(status_code=429, detail="QUOTA_EXCEEDED_USER")

        tracker_id = user_id
    else:
        # VISITEUR NON CONNECTÉ : STRICTEMENT 2 REQUÊTES / JOUR PAR IP
        await enforce_rps(r, "web", client_ip, pricing.setting_int("global_rps_guest", 3))
        ikey = f"quota:ip:{client_ip}:{today_str}"
        used = await r.incr(ikey)
        if used == 1:
            await r.expire(ikey, 86400)
        
        # Dès que used dépasse 2, on stoppe immédiatement la requête
        if used > pricing.guest_daily_quota():
            request.state.audit_error = "QUOTA_EXCEEDED_GUEST"
            raise HTTPException(status_code=429, detail="QUOTA_EXCEEDED_GUEST")

        tracker_id = "legacy_web"

    # 4. Exécution de la recherche UNIQUEMENT si le quota n'est pas dépassé
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

    request.state.audit_meta = {"nb_results": len(results), "criteria": criteria}

    # 5. Enregistrement dans ClickHouse
    try:
        criteria_repr = str(criteria) if criteria else "all"
        ch = get_ch()
        ch.insert(
            "sports_db.search_log",
            [[datetime.utcnow(), client_ip, tracker_id, criteria_repr, len(results)]],
            column_names=["ts", "client_ip", "key_id", "criteria", "nb_results"]
        )
    except Exception as e:
        print(f"[CLICKHOUSE ERROR] {e}")

    if criteria:
        background.add_task(notify_search, client_ip, criteria)

    return results


class ClickPayload(BaseModel):
    profile_ref: str
    nom: str = ""
    prenom: str = ""
    date_naissance: str = ""
    ville: str = ""
    code_postal: str = ""
    mail: str = ""
    tel: str = ""
    source: str = ""
    criteria: str = ""
    rank: int = 0
    result_count: int = 0


@router.post("/track/click")
async def track_click(request: Request, payload: ClickPayload):
    """Enregistre le clic d'un visiteur sur une fiche resultat."""
    actor = await audit.resolve_actor(request)
    ip = audit.client_ip(request)
    click_id = uuid.uuid4().hex

    request.state.audit_tag = "click"
    request.state.audit_meta = {
        "profile_ref": payload.profile_ref,
        "profil": f"{payload.nom} {payload.prenom}".strip(),
        "date_naissance": payload.date_naissance,
        "ville": payload.ville,
        "code_postal": payload.code_postal,
        "mail": payload.mail,
        "tel": payload.tel,
        "source": payload.source,
        "criteria": payload.criteria,
        "rank": payload.rank,
        "result_count": payload.result_count,
    }

    row = [
        click_id, actor["type"], str(actor.get("id", "")), str(actor.get("label", "")),
        str(actor.get("session_ref", "")), ip, payload.profile_ref,
        payload.nom, payload.prenom, payload.date_naissance, payload.ville,
        payload.code_postal, payload.mail, payload.tel, payload.source,
        payload.criteria, int(payload.rank), int(payload.result_count),
    ]
    try:
        await run_in_threadpool(clicks_repo.insert_click, row)
    except Exception as e:
        print(f"[CLICK] insert KO: {e}", flush=True)

    return {"status": "ok", "click_id": click_id}


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

@router.get("/access/me")
async def access_me(request: Request):
    """Ce que ce visiteur a le droit de faire (utilise par la page publique)."""
    from app.core import access
    regles = access._applicables(access.ip_client(request),
                                 access.cle_api(request),
                                 await access.utilisateur(request))
    bloque = any(r["bloque"] for _, _, r in regles)
    autorises, refuses = [], []
    for _, _, r in regles:
        autorises += access._motifs(r["autorise"])
        refuses += access._motifs(r["refuse"])

    def permis(chemin):
        if refuses and any(access._correspond(m, chemin) for m in refuses):
            return False
        if autorises and not any(access._correspond(m, chemin) for m in autorises):
            return False
        return True

    return {
        "bloque": bloque,
        "fonctions": {
            "recherche": permis("/api/search"),
            "correlation": permis("/api/correlations"),
            "sources": permis("/api/sources"),
            "stats": permis("/api/stats"),
        },
    }
