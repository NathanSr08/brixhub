"""Mode maintenance : bascule des pages publiques et blocage de la recherche."""
from __future__ import annotations

import os

from fastapi import Request

from app.core import pricing


def is_on() -> bool:
    return pricing.setting_bool("maintenance_mode", False)


def bypassed(request: Request) -> bool:
    tok = os.getenv("ADMIN_TOKEN", "")
    if not tok:
        return False
    q = request.query_params.get("bypass")
    if q and q == tok:
        return True
    return request.cookies.get("bx_bypass") == tok


def blocking(request: Request) -> bool:
    return is_on() and not bypassed(request)
