from fastapi import APIRouter, Query, Depends
from app.core.deps import require_api_key
from app.services.correlation_service import CorrelationService

router = APIRouter(tags=["correlations"])
svc = CorrelationService()

@router.get("/correlations", dependencies=[Depends(require_api_key)])
async def get_correlations(
    nom: str = Query(""),
    prenom: str = Query(""),
    date_naissance: str = Query(""),
    tel: str = Query(""),
    mail: str = Query(""),
    code_postal: str = Query(""),
    adresse: str = Query(""),
    source: str = Query("")
):
    return await svc.get_correlations(
        nom=nom,
        prenom=prenom,
        date_naissance=date_naissance,
        tel=tel,
        mail=mail,
        code_postal=code_postal,
        adresse=adresse,
        source=source
    )
