from starlette.concurrency import run_in_threadpool
from app.repositories import membres_repo

class CorrelationService:
    async def get_correlations(
        self,
        nom: str = "",
        prenom: str = "",
        date_naissance: str = "",
        tel: str = "",
        mail: str = "",
        code_postal: str = "",
        adresse: str = "",
        source: str = ""
    ) -> dict:
        nom = nom.strip()
        prenom = prenom.strip()
        tel = tel.strip()
        mail = mail.strip()
        cp = code_postal.strip()
        date_n = date_naissance.strip().replace('/', '-')

        matches = []
        family = []

        same_person_conds = []
        params_match = {"source": source}

        if nom and prenom:
            same_person_conds.append("(lower(nom) = lower(%(nom)s) AND lower(prenom) = lower(%(prenom)s))")
            params_match["nom"] = nom
            params_match["prenom"] = prenom

        if tel and len(tel) >= 8:
            same_person_conds.append("position(numero_tel, %(tel)s) > 0")
            params_match["tel"] = tel

        if mail and "@" in mail:
            same_person_conds.append("lower(mail) = lower(%(mail)s)")
            params_match["mail"] = mail

        if same_person_conds:
            q_match = f"""
                SELECT nom, prenom, date_naissance, mail, code_postal, ville, adresse, numero_tel, iban, bic, source
                FROM sports_db.membres
                WHERE ({" OR ".join(same_person_conds)})
                  AND source != %(source)s
                LIMIT 50
            """
            try:
                rows = await run_in_threadpool(membres_repo.raw_query, q_match, params_match)
                for r in rows:
                    r_nom, r_prenom, r_dn, r_mail, r_cp, r_ville, r_adr, r_tel, r_iban, r_bic, r_src = r
                    r_dn_norm = r_dn.replace('/', '-')

                    score = 0
                    reasons = []

                    if tel and r_tel and (tel in r_tel or r_tel in tel):
                        score += 45
                        reasons.append("Téléphone identique")

                    if mail and r_mail and mail.lower() == r_mail.lower():
                        score += 45
                        reasons.append("Email identique")

                    if nom and r_nom and nom.lower() == r_nom.lower():
                        if prenom and r_prenom and prenom.lower() == r_prenom.lower():
                            score += 30
                            reasons.append("Nom et Prénom identiques")

                    if date_n and r_dn_norm and date_n == r_dn_norm:
                        score += 35
                        reasons.append("Date de naissance exacte")

                    if cp and r_cp and cp == r_cp:
                        score += 15
                        reasons.append("Même Code Postal")

                    score = min(100, score)

                    if score >= 40:
                        matches.append({
                            "score": score,
                            "reasons": reasons,
                            "data": {
                                "Nom": r_nom, "Prenom": r_prenom, "Date de naissance": r_dn,
                                "mail": r_mail, "code postal": r_cp, "ville": r_ville,
                                "adresse": r_adr, "numero de tel": r_tel, "iban": r_iban,
                                "bic": r_bic, "source": r_src
                            }
                        })
            except Exception:
                pass

        matches.sort(key=lambda x: x["score"], reverse=True)

        if nom and (cp or adresse):
            family_conds = ["lower(nom) = lower(%(nom)s)"]
            params_fam = {"nom": nom}

            if prenom:
                family_conds.append("lower(prenom) != lower(%(prenom)s)")
                params_fam["prenom"] = prenom

            loc_conds = []
            if cp:
                loc_conds.append("code_postal = %(cp)s")
                params_fam["cp"] = cp
            if adresse and len(adresse) > 6:
                loc_conds.append("position(lower(adresse), lower(%(adr)s)) > 0")
                params_fam["adr"] = adresse[:15]

            if loc_conds:
                family_conds.append(f"({' OR '.join(loc_conds)})")

            q_fam = f"""
                SELECT nom, prenom, date_naissance, mail, code_postal, ville, adresse, numero_tel, iban, bic, source
                FROM sports_db.membres
                WHERE {" AND ".join(family_conds)}
                LIMIT 30
            """
            try:
                rows_fam = await run_in_threadpool(membres_repo.raw_query, q_fam, params_fam)
                for r in rows_fam:
                    r_nom, r_prenom, r_dn, r_mail, r_cp, r_ville, r_adr, r_tel, r_iban, r_bic, r_src = r

                    f_score = 40
                    f_reasons = ["Même Nom de famille"]

                    if adresse and r_adr and (adresse.lower() in r_adr.lower() or r_adr.lower() in adresse.lower()):
                        f_score += 40
                        f_reasons.append("Adresse de résidence identique")
                    elif cp and r_cp and cp == r_cp:
                        f_score += 20
                        f_reasons.append("Même Commune / Code postal")

                    if tel and r_tel and (tel[:6] == r_tel[:6] and (tel.startswith("01") or tel.startswith("02") or tel.startswith("03") or tel.startswith("04") or tel.startswith("05"))):
                        f_score += 20
                        f_reasons.append("Téléphone fixe du foyer")

                    f_score = min(100, f_score)

                    family.append({
                        "score": f_score,
                        "reasons": f_reasons,
                        "data": {
                            "Nom": r_nom, "Prenom": r_prenom, "Date de naissance": r_dn,
                            "mail": r_mail, "code postal": r_cp, "ville": r_ville,
                            "adresse": r_adr, "numero de tel": r_tel, "iban": r_iban,
                            "bic": r_bic, "source": r_src
                        }
                    })
            except Exception:
                pass

        family.sort(key=lambda x: x["score"], reverse=True)

        return {
            "matches": matches,
            "family": family
        }
