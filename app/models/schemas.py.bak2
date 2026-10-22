from typing import Optional
from pydantic import BaseModel, Field

class MembreRecord(BaseModel):
    nom: str = Field("", alias="Nom")
    prenom: str = Field("", alias="Prenom")
    date_naissance: str = Field("", alias="Date de naissance")
    annee_naissance: str = Field("", alias="annee de naissance")
    mois_naissance: str = Field("", alias="mois de naissance")
    jour_naissance: str = Field("", alias="jour de naissance")
    mail: str = ""
    code_postal: str = Field("", alias="code postal")
    ville: str = ""
    adresse: str = ""
    numero_tel: str = Field("", alias="numero de tel")
    iban: str = ""
    bic: str = ""
    source: str = ""

    class Config:
        populate_by_name = True

class KeyCreate(BaseModel):
    label: str = Field(..., min_length=1, max_length=80)
    owner_email: str = Field(..., min_length=3, max_length=120)
    plan: str = "free"

class KeyOut(BaseModel):
    key: Optional[str] = None
    key_id: str
    preview: str
    label: str
    owner_email: str
    plan: str
    quota_per_day: int
    is_active: bool
