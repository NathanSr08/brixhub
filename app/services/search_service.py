from typing import Optional
from starlette.concurrency import run_in_threadpool
from app.repositories import membres_repo
import hashlib

from app.core.normalizer import normalize_name, normalize_phone, get_name_variants


def profile_ref(nom, prenom, date_naissance, code_postal, source) -> str:
    """Identifiant deterministe d'une fiche (stable entre deux recherches)."""
    raw = "|".join(str(x or "").strip().upper()
                   for x in (nom, prenom, date_naissance, code_postal, source))
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]

def _build_conditions(**f) -> tuple[list[str], dict]:
    conditions, params = [], {}

    # 1. Recherche Globale q
    if f.get("q"):
        raw_q = f["q"].strip()
        tokens = raw_q.split()

        # Si c'est un numéro
        phone_vars = normalize_phone(raw_q)
        if phone_vars:
            conditions.append("(numero_tel IN %(q_phones)s OR position(numero_tel, %(q_core)s) > 0)")
            params["q_phones"] = phone_vars
            params["q_core"] = phone_vars[0][-9:] if len(phone_vars[0]) >= 9 else phone_vars[0]

        # Si 2 tokens (ex: "Alex Dupont") -> inversion rapide
        elif len(tokens) == 2:
            t1, t2 = tokens[0].strip(), tokens[1].strip()
            conditions.append("""(
                (ilike(nom, %(t1)s) AND ilike(prenom, %(t2)s))
                OR (ilike(nom, %(t2)s) AND ilike(prenom, %(t1)s))
                OR ilike(mail, %(q_full)s)
            )""")
            params["t1"] = f"{t1}%"
            params["t2"] = f"{t2}%"
            params["q_full"] = f"%{raw_q}%"

        else:
            for idx, token in enumerate(tokens):
                p = f"q_{idx}"
                conditions.append(f"""(
                    ilike(nom, %({p})s) OR ilike(prenom, %({p})s) OR
                    ilike(mail, %({p}_full)s) OR ilike(ville, %({p})s) OR
                    position(numero_tel, %({p}_raw)s) > 0
                )""")
                params[p] = f"{token}%"
                params[f"{p}_full"] = f"%{token}%"
                params[f"{p}_raw"] = token

    # 2. Nom (utilise l'index primaire ORDER BY nom)
    if f.get("nom"):
        n = f["nom"].strip()
        # Égalité directe ou préfixe (très rapide avec l'index)
        conditions.append("(nom = %(nom)s OR ilike(nom, %(nom_prefix)s))")
        params["nom"] = n.upper()
        params["nom_prefix"] = f"{n}%"

    # 3. Prénom
    if f.get("prenom"):
        p = f["prenom"].strip()
        p_vars = [v.upper() for v in get_name_variants(p)]
        conditions.append("(prenom IN %(p_vars)s OR ilike(prenom, %(p_prefix)s))")
        params["p_vars"] = p_vars
        params["p_prefix"] = f"{p}%"

    # 4. Dates
    if f.get("date_naissance"):
        raw = f["date_naissance"].strip()
        conditions.append("(date_naissance = %(dr)s OR date_naissance = %(dn)s)")
        params["dr"] = raw
        params["dn"] = raw.replace("/", "-")

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

    # 5. Localisation
    if f.get("code_postal"):
        conditions.append("code_postal = %(cp)s")
        params["cp"] = f["code_postal"].strip()

    if f.get("ville"):
        conditions.append("ilike(ville, %(ville)s)")
        params["ville"] = f"{f['ville'].strip()}%"

    # 6. Téléphone (rapide : lookup IN direct sur les formats possibles)
    if f.get("tel"):
        t_raw = f["tel"].strip()
        phone_vars = normalize_phone(t_raw)
        if phone_vars:
            conditions.append("(numero_tel IN %(tel_vars)s OR position(numero_tel, %(tel_core)s) > 0)")
            params["tel_vars"] = phone_vars
            core = phone_vars[0][-9:] if len(phone_vars[0]) >= 9 else phone_vars[0]
            params["tel_core"] = core
        else:
            conditions.append("position(numero_tel, %(tel)s) > 0")
            params["tel"] = t_raw

    # 7. Mail & Source
    if f.get("mail"):
        conditions.append("mail = %(mail)s")
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
        clause_str = " AND ".join(conditions)
        where = f"WHERE {clause_str}"
        rows = await run_in_threadpool(membres_repo.search, where, params, limit)
        keys = ["Nom", "Prenom", "Date de naissance", "annee de naissance",
                "mois de naissance", "jour de naissance", "mail", "code postal",
                "ville", "adresse", "numero de tel", "iban", "bic", "source"]
        out = []
        for r in rows:
            d = dict(zip(keys, r))
            d["profile_ref"] = profile_ref(d.get("Nom"), d.get("Prenom"),
                                           d.get("Date de naissance"),
                                           d.get("code postal"), d.get("source"))
            out.append(d)
        return out

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
