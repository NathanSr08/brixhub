#!/usr/bin/env python3
"""Exclut les logs admin par defaut (filtre exclude_admin)."""
import shutil
import sys
from pathlib import Path

ROOT = Path.cwd()
if not (ROOT / "app" / "main.py").exists():
    print("!!! Lance depuis la racine du repo"); sys.exit(2)

DONE, SKIPPED, FAILED = [], [], []
ADMIN_COND = " AND tag != 'admin' AND actor_type != 'admin'"


def load(p): return (ROOT / p).read_text(encoding="utf-8")


def save(p, s):
    f = ROOT / p
    bak = f.with_suffix(f.suffix + ".bak3")
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


# ============================ audit_repo.py ============================ #
P = "app/repositories/audit_repo.py"

# 1. _where : exclure aussi l'admin
replace(P,
    '''    if f.get("exclude_panel", True):
        c.append("tag != 'panel'")
    return (" AND ".join(c) if c else "1"), p''',
    '''    if f.get("exclude_panel", True):
        c.append("tag != 'panel'")
    if f.get("exclude_admin", True):
        c.append("tag != 'admin'")
        c.append("actor_type != 'admin'")
    return (" AND ".join(c) if c else "1"), p''',
    'c.append("actor_type != \'admin\'")', "audit_repo._where : exclude_admin")

# 2. where_literal : idem (utilise par la purge)
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
    'c.append("tag != \'admin\'")', "audit_repo.where_literal : exclude_admin")

# 3. logs_since : parametre exclude_admin
replace(P,
    "def logs_since(epoch: float, limit: int = 200) -> list[dict]:\n    res = get_ch().query(",
    "def logs_since(epoch: float, limit: int = 200, exclude_admin: bool = True) -> list[dict]:\n"
    '    extra = ADMIN_COND if exclude_admin else ""\n'
    "    res = get_ch().query(",
    "exclude_admin: bool = True) -> list[dict]", "audit_repo.logs_since : signature")

# 4. stats : parametre exclude_admin
replace(P,
    "def stats(hours: int = 24) -> dict:\n    res = get_ch().query(",
    "def stats(hours: int = 24, exclude_admin: bool = True) -> dict:\n"
    '    extra = ADMIN_COND if exclude_admin else ""\n'
    "    res = get_ch().query(",
    "exclude_admin: bool = True) -> dict", "audit_repo.stats : signature")

# 5. injecter {extra} dans tous les WHERE des deux fonctions
s = load(P)
if "{extra}" not in s:
    n = s.count("AND tag != 'panel'")
    s = s.replace("AND tag != 'panel'", "AND tag != 'panel'{extra}")
    # constante au niveau module
    if "ADMIN_COND =" not in s:
        s = s.replace('TABLE = "auth_db.api_logs"',
                      'TABLE = "auth_db.api_logs"\n'
                      'ADMIN_COND = " AND tag != \'admin\' AND actor_type != \'admin\'"', 1)
    save(P, s)
    DONE.append(f"audit_repo : {{extra}} injecte ({n} occurrences)")
else:
    SKIPPED.append("audit_repo : {extra} deja injecte")

# ============================ admin_logs.py ============================ #
P = "app/api/admin_logs.py"

replace(P,
    "    exclude_panel: bool = True, limit: int = 100, offset: int = 0,\n):",
    "    exclude_panel: bool = True, exclude_admin: bool = True,\n"
    "    limit: int = 100, offset: int = 0,\n):",
    "exclude_panel: bool = True, exclude_admin: bool = True",
    "admin_logs.api_logs : parametre")

replace(P,
    '    f["exclude_panel"] = exclude_panel',
    '    f["exclude_panel"] = exclude_panel\n    f["exclude_admin"] = exclude_admin',
    'f["exclude_admin"] = exclude_admin', "admin_logs.api_logs : filtre")

replace(P,
    "async def api_logs_stats(hours: int = 24):\n"
    "    await audit.flush_now()\n"
    "    return await run_in_threadpool(audit_repo.stats, max(1, min(hours, 720)))",
    "async def api_logs_stats(hours: int = 24, exclude_admin: bool = True):\n"
    "    await audit.flush_now()\n"
    "    return await run_in_threadpool(audit_repo.stats, max(1, min(hours, 720)), exclude_admin)",
    "audit_repo.stats, max(1, min(hours, 720)), exclude_admin",
    "admin_logs.api_logs_stats : exclude_admin")

replace(P,
    'async def api_logs_stream(request: Request, actor_type: str = "all", q: str = ""):',
    'async def api_logs_stream(request: Request, actor_type: str = "all", q: str = "",\n'
    '                          exclude_admin: bool = True):',
    "q: str = \"\",\n                          exclude_admin: bool = True",
    "admin_logs.api_logs_stream : parametre")

replace(P,
    "rows = await run_in_threadpool(audit_repo.logs_since, last, 200)",
    "rows = await run_in_threadpool(audit_repo.logs_since, last, 200, exclude_admin)",
    "audit_repo.logs_since, last, 200, exclude_admin",
    "admin_logs.api_logs_stream : exclude_admin")

# ============================ logs.js (x2) ============================ #
for P in ["app/static/logs.js", "static/logs.js"]:
    if not (ROOT / P).exists():
        continue

    replace(P,
        '> Inclure le panel</label>',
        '> Inclure admin &amp; panel</label>',
        "Inclure admin &amp; panel", f"{P} : libelle case")

    replace(P,
        "    if (document.getElementById('logIncludePanel').checked) p.set('exclude_panel', 'false');",
        "    if (document.getElementById('logIncludePanel').checked) {\n"
        "        p.set('exclude_panel', 'false');\n"
        "        p.set('exclude_admin', 'false');\n"
        "    }",
        "p.set('exclude_admin', 'false')", f"{P} : logParams")

    replace(P,
        "        var res = await fetch('/admin/api/logs/stats?hours=24');",
        "        var inc = document.getElementById('logIncludePanel');\n"
        "        var res = await fetch('/admin/api/logs/stats?hours=24&exclude_admin='\n"
        "            + (inc && inc.checked ? 'false' : 'true'));",
        "exclude_admin=' + (inc && inc.checked", f"{P} : fetchLogsStats")

print("\n=== PATCH ===")
for d in DONE: print("  [OK]   ", d)
for s_ in SKIPPED: print("  [SKIP] ", s_)
for f in FAILED: print("  [ECHEC]", f)
print(f"\n{len(DONE)} applique(s), {len(SKIPPED)} deja en place, {len(FAILED)} echec(s).")
sys.exit(1 if FAILED else 0)
