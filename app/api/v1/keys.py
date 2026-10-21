from fastapi import APIRouter, Header, HTTPException, Depends
from app.models.schemas import KeyCreate, KeyOut
from app.core.config import get_settings
from app.core.deps import require_api_key
from app.services.key_service import KeyService

router = APIRouter(prefix="/keys", tags=["keys"])
svc = KeyService()

def require_admin(x_admin_token: str = Header(None)):
    if x_admin_token != get_settings().admin_token:
        raise HTTPException(status_code=403, detail="Token admin invalide")

@router.post("", response_model=KeyOut, dependencies=[Depends(require_admin)])
async def create_key(payload: KeyCreate):
    return await svc.create(payload.label, payload.owner_email, payload.plan)

@router.delete("/{key_id}", dependencies=[Depends(require_admin)])
async def revoke_key(key_id: str):
    ok = await svc.revoke(key_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Cle introuvable")
    return {"status": "revoked", "key_id": key_id}

@router.get("/me")
async def get_my_usage(key: dict = Depends(require_api_key)):
    return await svc.usage(key["key_id"])
