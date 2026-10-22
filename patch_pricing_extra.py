#!/usr/bin/env python3
import shutil
import sys
from pathlib import Path

ROOT = Path.cwd()
DONE, SKIPPED, FAILED = [], [], []


def load(p): return (ROOT / p).read_text(encoding="utf-8")


def save(p, s):
    f = ROOT / p
    bak = f.with_suffix(f.suffix + ".bakextra")
    if not bak.exists():
        shutil.copy2(f, bak)
    f.write_text(s, encoding="utf-8")


def replace(path, old, new, marker, label):
    s = load(path)
    if marker in s:
        SKIPPED.append(label); return
    if old not in s:
        FAILED.append(f"{label} : ancre introuvable"); return
    save(path, s.replace(old, new, 1))
    DONE.append(label)


# --- nouveaux reglages ---
P = "app/repositories/pricing_repo.py"
replace(P,
    '    "price_format_eur": "{value} EUR",',
    '''    "pricing_title": "Plans & Licences API",
    "pricing_subtitle": "Acces direct et sans engagement avec quotas journaliers reinitialises a 00:00 UTC.",
    "recommended_plan": "pro",
    "cta_url": "/",
    "cta_label": "Prendre {plan} ({price})",
    "contact_url": "mailto:contact@brixhub.uned.live",
    "contact_label": "Contacter l'equipe",
    "price_format_eur": "{value} EUR",''',
    "pricing_title", "pricing_repo : reglages tarifs")

# --- exposition dans la config publique ---
P = "app/core/pricing.py"
replace(P,
    '        "price_format_eur": s.get("price_format_eur", "{value} EUR"),',
    '''        "pricing_title": s.get("pricing_title", ""),
        "pricing_subtitle": s.get("pricing_subtitle", ""),
        "recommended_plan": s.get("recommended_plan", "pro"),
        "cta_url": s.get("cta_url", "/"),
        "cta_label": s.get("cta_label", "Prendre {plan} ({price})"),
        "contact_url": s.get("contact_url", "mailto:contact@brixhub.uned.live"),
        "contact_label": s.get("contact_label", "Contacter l'equipe"),
        "price_format_eur": s.get("price_format_eur", "{value} EUR"),''',
    "pricing_title", "pricing.py : config publique")

print("\n=== PATCH ===")
for d in DONE: print("  [OK]   ", d)
for s_ in SKIPPED: print("  [SKIP] ", s_)
for f in FAILED: print("  [ECHEC]", f)
sys.exit(1 if FAILED else 0)
