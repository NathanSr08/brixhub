from typing import Optional
from starlette.concurrency import run_in_threadpool
from app.repositories import membres_repo

def _build_conditions(**f) -> tuple[list[str], dict]:
    conditions, params = [], {}

    if f.get("q"):
        for idx, token in enumerate(f["q"].strip().split()):
            p = f"q_{idx}"
            conditions.append(f"""(
                ilike(nom, %({p})s) OR ilike(prenom, %({p})s) OR
                ilike(mail, %({p})s) OR ilike(ville, %({p})s) OR
                ilike(adresse, %({p})s) OR position(numero_tel, %({p}_raw)s) > 0
            )""")
            params[p] = f"%{token}%"
            params[f"{p}_raw"] = token

    if f.get("nom"):
        conditions.append("lower(nom) = lower(%(nom)s)")
        params["nom"] = f["nom"].strip()
    if f.get("prenom"):
        conditions.append("lower(prenom) = lower(%(prenom)s)")
        params["prenom"] = f["prenom"].strip()

    if f.get("date_naissance"):
        raw = f["date_naissance"].strip()
        conditions.append("(replaceAll(date_naissance, '/', '-') = %(dn)s OR date_naissance = %(dr)s)")
        params["dn"], params["dr"] = raw.replace("/", "-"), raw

    if f.get("jour"):
        j = f["jour"].strip()
        conditions.append("(jour_naissance = %(j)s OR jour_naissance = %(jr)s)")
        params["j"], params["jr"] = j.zfill(2), str(int(j)) if j.isdigit() else j
    if f.get("mois"):
        m = f["mois"].strip()
        conditions.append("(mois_naissance = %(m)s OR mois_naissance = %(mr)s)")
        params["m"], params["mr"] = m.zfill(2), str(int(m)) if m.isdigit() else m
    if f.get("annee"):
        conditions.append("annee_naissance = %(annee)s")
        params["annee"] = f["annee"].strip()

    if f.get("code_postal"):
        conditions.append("code_postal = %(cp)s")
        params["cp"] = f["code_postal"].strip()
    if f.get("ville"):
        conditions.append("ilike(ville, %(ville)s)")
        params["ville"] = f"%{f['ville'].strip()}%"
    if f.get("tel"):
        conditions.append("position(numero_tel, %(tel)s) > 0")
        params["tel"] = f["tel"].strip()
    if f.get("mail"):
        conditions.append("lower(mail) = lower(%(mail)s)")
        params["mail"] = f["mail"].strip()
    if f.get("source") and f["source"] != "ALL":
        conditions.append("source = %(source)s")
        params["source"] = f["source"].strip()

    return conditions, params

class SearchService:
    async def search(self, limit: int = 100, **filters) -> list[dict]:
        conditions, params = _build_conditions(**filters)
        if not conditions:
            return []
        where = f"WHERE {' AND '.join(conditions)}"
        rows = await run_in_threadpool(membres_repo.search, where, params, limit)
        keys = ["Nom", "Prenom", "Date de naissance", "annee de naissance",
                "mois de naissance", "jour de naissance", "mail", "code postal",
                "ville", "adresse", "numero de tel", "iban", "bic", "source"]
        return [dict(zip(keys, r)) for r in rows]

    async def stats(self) -> dict:
        total, by_source = await run_in_threadpool(
            lambda: (membres_repo.total_rows(), membres_repo.count_by_source()))
        return {"total": total, "by_source": by_source}

    async def sources(self) -> list[str]:
        return await run_in_threadpool(membres_repo.list_sources)

    @staticmethod
    def criteria_from(filters: dict) -> dict:
        labels = {"q": "Recherche globale", "nom": "Nom", "prenom": "Prénom",
                  "date_naissance": "Date de naissance", "jour": "Jour", "mois": "Mois",
                  "annee": "Année", "code_postal": "Code postal", "ville": "Ville",
                  "tel": "Téléphone", "mail": "Email", "source": "Source"}
        return {labels[k]: v for k, v in filters.items()
                if v and not (k == "source" and v == "ALL")}
