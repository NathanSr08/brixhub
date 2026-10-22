#!/usr/bin/env python3
import shutil
import sys
from pathlib import Path

ROOT = Path.cwd()
DONE, SKIPPED, FAILED = [], [], []


def load(p): return (ROOT / p).read_text(encoding="utf-8")


def save(p, s):
    f = ROOT / p
    bak = f.with_suffix(f.suffix + ".bakdetect")
    if not bak.exists():
        shutil.copy2(f, bak)
    f.write_text(s, encoding="utf-8")


def replace(path, old, new, marker, label):
    s = load(path)
    if marker in s:
        SKIPPED.append(label); return
    if old not in s:
        FAILED.append(f"{label} : ancre introuvable dans {path}"); return
    save(path, s.replace(old, new, 1))
    DONE.append(label)


# ---- defaut de banniere plus clair ----
P = "app/repositories/pricing_repo.py"
replace(P,
    '"banner_text": "",',
    '"banner_text": "Nouvelle grille tarifaire disponible - voir la documentation API",',
    '"banner_text": "Nouvelle grille tarifaire', "pricing_repo : texte banniere par defaut")

# ---- endpoint de detection ----
P = "app/api/admin_pricing.py"
replace(P,
    "def _ip(request: Request) -> str:",
    '''@router.post("/api/pricing/detect", dependencies=[Depends(require_admin_auth)])
async def admin_detect_ui_matches(request: Request):
    """Scanne les pages publiques et remplit automatiquement les champs
    'texte a remplacer' des plans, en associant chaque libelle a son prix."""
    import html as htmlmod
    import re
    import urllib.request

    base = str(request.base_url).rstrip("/")

    def _plain(path: str) -> str:
        try:
            raw = urllib.request.urlopen(base + path, timeout=10).read().decode("utf-8", "ignore")
        except Exception:
            return ""
        raw = re.sub(r"<script.*?</script>", " ", raw, flags=re.S | re.I)
        raw = re.sub(r"<style.*?</style>", " ", raw, flags=re.S | re.I)
        txt = htmlmod.unescape(re.sub(r"<[^>]+>", " ", raw))
        return re.sub(r"\\s+", " ", txt)

    pages = {}
    for path in ("/", "/api-docs", "/cgu"):
        p = _plain(path)
        if p:
            pages[path] = p

    def _work():
        found = {}
        plans = pricing_repo.list_plans() + pricing_repo.list_deletion_plans()
        price_re = re.compile(r"\\d+(?:[.,]\\d{1,2})?\\s*(?:€|EUR|\\$|USD)", re.I)
        for pl in plans:
            label = (pl.get("label") or pl["plan_id"]).strip()
            if not label:
                continue
            for path, txt in pages.items():
                idx = txt.lower().find(label.lower())
                if idx == -1:
                    continue
                window = txt[max(0, idx - 150): idx + 450]
                m = price_re.search(window)
                if m:
                    found[pl["plan_id"]] = {"ui_match": m.group(0).strip(), "page": path}
                break

        applied = []
        for pid, info in found.items():
            target = next((x for x in pricing_repo.list_plans() if x["plan_id"] == pid), None)
            kind = "plan"
            if target is None:
                target = next((x for x in pricing_repo.list_deletion_plans()
                               if x["plan_id"] == pid), None)
                kind = "deletion"
            if target is None:
                continue
            target["ui_match"] = info["ui_match"]
            if kind == "plan":
                pricing_repo.upsert_plan(target)
            else:
                pricing_repo.upsert_deletion_plan(target)
            applied.append({"plan_id": pid, "ui_match": info["ui_match"], "page": info["page"]})

        return {"pages_scannees": list(pages.keys()), "appliques": applied}

    result = await run_in_threadpool(_work)
    await pricing.invalidate()
    audit_repo.log_admin_action("admin", "pricing_detect", "ui_match",
                                str(len(result.get("appliques", []))), _ip(request))
    return result


def _ip(request: Request) -> str:''',
    "admin_detect_ui_matches", "admin_pricing : endpoint detect")

print("\n=== PATCH ===")
for d in DONE: print("  [OK]   ", d)
for s_ in SKIPPED: print("  [SKIP] ", s_)
for f in FAILED: print("  [ECHEC]", f)
sys.exit(1 if FAILED else 0)
