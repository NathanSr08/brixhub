from fastapi import APIRouter
from app.api.v1.search import router as search_router
from app.api.v1.correlations import router as correlations_router
from app.api.v1.misc import router as misc_router
from app.api.v1.keys import router as keys_router

api_v1 = APIRouter()
api_v1.include_router(search_router)
api_v1.include_router(correlations_router)
api_v1.include_router(misc_router)
api_v1.include_router(keys_router)

v1_router = api_v1
