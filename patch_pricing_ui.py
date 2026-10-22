#!/usr/bin/env python3
import shutil
import sys
from pathlib import Path

ROOT = Path.cwd()
DONE, SKIPPED, FAILED = [], [], []


def load(p): return (ROOT / p).read_text(encoding="utf-8")


def save(p, s):
    f = ROOT / p
    bak = f.with_suffix(f.suffix + ".bakuifix")
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


P = "app/static/pricing-admin.js"

# 1) reglages : cases a cocher pour les booleens + libelles clairs
replace(P,
    '''    window.loadSettings = async function () {
        var grid = document.getElementById('settingsGrid');
        try {
            var res = await fetch('/admin/api/settings');
            var d = await res.json();
            var v = d.values || {};
            grid.innerHTML = Object.keys(d.defaults || v).map(function (k) {
                var val = v[k] !== undefined ? v[k] : '';
                return '<div><div class="text-slate-400 mb-1">' + esc(LABELS[k] || k) +
                    '<span class="text-slate-600 font-mono ml-1">' + esc(k) + '</span></div>' +
                    '<input id="st_' + k + '" value="' + esc(val) + '" class="w-full bg-dark border border-slate-800 rounded px-2 py-1 text-[11px] text-white"></div>';
            }).join('');
            var rules = document.getElementById('uiRules');
            if (rules) rules.value = v.ui_rules || '[]';
        } catch (e) { grid.innerHTML = '<div class="text-red-400">Erreur</div>'; }
    };''',
    '''    var BOOLS = { registration_open: 1, maintenance_mode: 1, banner_enabled: 1 };
    var SELECTS = {
        banner_type: ['info', 'warning', 'danger', 'success']
    };

    window.loadSettings = async function () {
        var grid = document.getElementById('settingsGrid');
        try {
            var res = await fetch('/admin/api/settings');
            var d = await res.json();
            var v = d.values || {};
            grid.innerHTML = Object.keys(d.defaults || v).map(function (k) {
                var val = v[k] !== undefined ? v[k] : '';
                var field;
                if (BOOLS[k]) {
                    var on = String(val) === '1' || String(val).toLowerCase() === 'true';
                    field = '<label class="flex items-center gap-2 bg-dark border border-slate-800 rounded px-2 py-1.5">' +
                        '<input id="st_' + k + '" type="checkbox" class="accent-emerald-500" ' + (on ? 'checked' : '') + ' onchange="previewBanner()">' +
                        '<span class="text-slate-300">' + (on ? 'ACTIF' : 'inactif') + '</span></label>';
                } else if (SELECTS[k]) {
                    field = '<select id="st_' + k + '" class="w-full bg-dark border border-slate-800 rounded px-2 py-1 text-[11px] text-white">' +
                        SELECTS[k].map(function (o) {
                            return '<option value="' + o + '" ' + (o === val ? 'selected' : '') + '>' + o + '</option>';
                        }).join('') + '</select>';
                } else {
                    field = '<input id="st_' + k + '" value="' + esc(val) + '" class="w-full bg-dark border border-slate-800 rounded px-2 py-1 text-[11px] text-white">';
                }
                return '<div><div class="text-slate-400 mb-1">' + esc(LABELS[k] || k) +
                    '<span class="text-slate-600 font-mono ml-1">' + esc(k) + '</span></div>' + field + '</div>';
            }).join('');
            var rules = document.getElementById('uiRules');
            if (rules) rules.value = v.ui_rules || '[]';
            previewBanner();
        } catch (e) { grid.innerHTML = '<div class="text-red-400">Erreur</div>'; }
    };

    window.previewBanner = function () {
        var box = document.getElementById('bannerPreview');
        if (!box) return;
        var on = document.getElementById('st_banner_enabled');
        var txt = document.getElementById('st_banner_text');
        var typ = document.getElementById('st_banner_type');
        if (!on || !txt) return;
        var colors = {
            info: 'bg-blue-600/20 border-blue-700 text-blue-100',
            warning: 'bg-amber-600/20 border-amber-700 text-amber-100',
            danger: 'bg-red-600/20 border-red-700 text-red-100',
            success: 'bg-emerald-600/20 border-emerald-700 text-emerald-100'
        };
        var c = colors[typ ? typ.value : 'info'] || colors.info;
        box.innerHTML = on.checked
            ? '<div class="border rounded-lg px-3 py-2 text-[12px] ' + c + '"><i class="fa-solid fa-bullhorn mr-2"></i>' +
              esc(txt.value || 'Annonce BrixHub') + '</div>'
            : '<div class="text-slate-500 text-[11px]">Banniere desactivee</div>';
    };''',
    "previewBanner", "pricing-admin : reglages booléens")

# 2) saveSettings : lire les cases
replace(P,
    '''        var values = {};
        document.querySelectorAll('[id^="st_"]').forEach(function (el) {
            values[el.id.slice(3)] = el.value;
        });''',
    '''        var values = {};
        document.querySelectorAll('[id^="st_"]').forEach(function (el) {
            var k = el.id.slice(3);
            values[k] = BOOLS[k] ? (el.checked ? '1' : '0') : el.value;
        });''',
    "BOOLS[k] ? (el.checked", "pricing-admin : saveSettings bool")

# 3) bouton detecter + zone d'apercu banniere
replace(P,
    '''        <button onclick="flushPricingCache()" class="px-3 py-1.5 rounded-lg bg-slate-800 border border-slate-700 text-slate-200 text-[11px]">Vider le cache</button>''',
    '''        <button onclick="detectUiMatches()" class="px-3 py-1.5 rounded-lg bg-fuchsia-600 text-white text-[11px] font-semibold"><i class="fa-solid fa-magnifying-glass mr-1"></i>Detecter les prix des pages</button>
        <button onclick="flushPricingCache()" class="px-3 py-1.5 rounded-lg bg-slate-800 border border-slate-700 text-slate-200 text-[11px]">Vider le cache</button>''',
    "detectUiMatches", "pricing-admin : bouton detecter")

replace(P,
    '''    window.reloadPricing = function ()''',
    '''    window.detectUiMatches = async function () {
        var r = await fetch('/admin/api/pricing/detect', { method: 'POST' });
        if (!r.ok) { alert('Erreur de detection'); return; }
        var d = await r.json();
        var lines = (d.appliques || []).map(function (x) {
            return x.plan_id + '  ->  "' + x.ui_match + '"  (' + x.page + ')';
        });
        alert('Pages scannees : ' + (d.pages_scannees || []).join(', ') + '\\n\\n' +
              (lines.length ? 'Correspondances trouvees :\\n' + lines.join('\\n')
                            : 'Aucun prix trouve. Remplis le champ "Texte a remplacer" a la main.'));
        loadPlans();
    };

    window.reloadPricing = function ()''',
    "detectUiMatches = async function", "pricing-admin : fonction detect")

replace(P,
    '''    <div id="settingsGrid" class="p-4 grid md:grid-cols-2 xl:grid-cols-3 gap-3 text-[11px]"></div>''',
    '''    <div id="settingsGrid" class="p-4 grid md:grid-cols-2 xl:grid-cols-3 gap-3 text-[11px]"></div>
    <div class="px-4 pb-2">
      <div class="text-slate-400 text-[11px] mb-1">Apercu de la banniere</div>
      <div id="bannerPreview"></div>
    </div>''',
    "bannerPreview", "pricing-admin : zone apercu banniere")

print("\n=== PATCH ===")
for d in DONE: print("  [OK]   ", d)
for s_ in SKIPPED: print("  [SKIP] ", s_)
for f in FAILED: print("  [ECHEC]", f)
sys.exit(1 if FAILED else 0)
