#!/usr/bin/env python3
"""Correctifs : where_literal (purge), clicks_repo, cache-busting des scripts."""
import shutil
import sys
from pathlib import Path

ROOT = Path.cwd()
if not (ROOT / "app" / "main.py").exists():
    print("!!! Lance depuis la racine du repo"); sys.exit(2)

DONE, SKIPPED, FAILED = [], [], []


def load(p): return (ROOT / p).read_text(encoding="utf-8")


def save(p, s):
    f = ROOT / p
    bak = f.with_suffix(f.suffix + ".bak3b")
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


# ---------- 1. audit_repo.where_literal : ajouter exclude_admin ----------
P = "app/repositories/audit_repo.py"
replace(P,
    '''    if f.get("exclude_panel", True):
        c.append("tag != 'panel'")
    return " AND ".join(c) if c else "1"''',
    '''    if f.get("exclude_panel", True):
        c.append("tag != 'panel'")
    if f.get("exclude_admin", True):
        c.append("tag != 'admin'")
        c.append("actor_type != 'admin'")
    return " AND ".join(c) if c else "1"''',
    'c.append("actor_type != \'admin\'")\n    return " AND ".join(c) if c else "1"',
    "audit_repo.where_literal : exclude_admin")

# ---------- 2. clicks_repo : meme filtre ----------
P = "app/repositories/clicks_repo.py"
replace(P,
    '''    if f.get("to_ts"):
        c.append("ts <= %(tts)s"); p["tts"] = str(f["to_ts"]).replace("T", " ")
    return (" AND ".join(c) if c else "1"), p''',
    '''    if f.get("to_ts"):
        c.append("ts <= %(tts)s"); p["tts"] = str(f["to_ts"]).replace("T", " ")
    if f.get("exclude_admin", True):
        c.append("actor_type != 'admin'")
    return (" AND ".join(c) if c else "1"), p''',
    "clicks_repo._where : exclude_admin", "clicks_repo._where : exclude_admin")

replace(P,
    '''    if f.get("to_ts"):
        c.append("ts <= " + esc_lit(str(f["to_ts"]).replace("T", " ")))
    return " AND ".join(c) if c else "1"''',
    '''    if f.get("to_ts"):
        c.append("ts <= " + esc_lit(str(f["to_ts"]).replace("T", " ")))
    if f.get("exclude_admin", True):
        c.append("actor_type != 'admin'")
    return " AND ".join(c) if c else "1"''',
    "clicks_repo.where_literal : exclude_admin", "clicks_repo.where_literal : exclude_admin")

# ---------- 3. endpoint /api/clicks : parametre explicite ----------
P = "app/api/admin_logs.py"
replace(P,
    '''    q: str = "", actor_type: str = "all", actor_id: str = "", ip: str = "",
    profile_ref: str = "", from_ts: str = "", to_ts: str = "",
    limit: int = 100, offset: int = 0,
):
    f = _filters(q=q, actor_type=actor_type, actor_id=actor_id, ip=ip,
                 profile_ref=profile_ref, from_ts=from_ts, to_ts=to_ts)''',
    '''    q: str = "", actor_type: str = "all", actor_id: str = "", ip: str = "",
    profile_ref: str = "", from_ts: str = "", to_ts: str = "",
    exclude_admin: bool = True, limit: int = 100, offset: int = 0,
):
    f = _filters(q=q, actor_type=actor_type, actor_id=actor_id, ip=ip,
                 profile_ref=profile_ref, from_ts=from_ts, to_ts=to_ts)
    f["exclude_admin"] = exclude_admin''',
    'f["exclude_admin"] = exclude_admin', "admin_logs.api_clicks : exclude_admin")

# ---------- 4. cache-busting des scripts injectes ----------
for P in ["app/static/admin.html", "static/admin.html"]:
    if not (ROOT / P).exists():
        continue
    replace(P,
        '<script src="/static/logs.js"></script>',
        '<script src="/static/logs.js?v=3"></script>',
        "/static/logs.js?v=3", f"{P} : version logs.js")
    replace(P,
        '<script src="/static/logs-extra.js"></script>',
        '<script src="/static/logs-extra.js?v=3"></script>',
        "/static/logs-extra.js?v=3", f"{P} : version logs-extra.js")

for P in ["app/static/index.html", "static/index.html"]:
    if not (ROOT / P).exists():
        continue
    replace(P,
        '<script src="/static/track-click.js"></script>',
        '<script src="/static/track-click.js?v=3"></script>',
        "/static/track-click.js?v=3", f"{P} : version track-click.js")

print("\n=== PATCH ===")
for d in DONE: print("  [OK]   ", d)
for s_ in SKIPPED: print("  [SKIP] ", s_)
for f in FAILED: print("  [ECHEC]", f)
print(f"\n{len(DONE)} applique(s), {len(SKIPPED)} deja en place, {len(FAILED)} echec(s).")
sys.exit(1 if FAILED else 0)
