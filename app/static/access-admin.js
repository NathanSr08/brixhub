/* BrixHub - onglet "Acces & Securite" : tout en listes deroulantes */
(function () {
  if (document.getElementById('tabBtnAccess')) return;
  var ref = document.getElementById('tabBtnWebAccess') || document.getElementById('tabBtnUsers');
  var hote = document.getElementById('tabContentUsers');
  if (!ref || !hote) return;

  var IDLE = "px-4 py-2 rounded-xl bg-surface hover:bg-slate-800 text-slate-400 hover:text-white transition flex items-center gap-2 border border-slate-800";
  var ACTIF = "px-4 py-2 rounded-xl bg-amber-600 text-white transition flex items-center gap-2";
  var SEL = "bg-dark border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200 w-full";

  var btn = document.createElement('button');
  btn.id = 'tabBtnAccess';
  btn.className = IDLE;
  btn.innerHTML = '<i class="fa-solid fa-shield-halved"></i> <span>Acces &amp; Securite</span>';
  btn.onclick = function () { window.switchMainTab('access'); };
  ref.insertAdjacentElement('afterend', btn);

  var sec = document.createElement('div');
  sec.id = 'tabContentAccess';
  sec.className = 'hidden space-y-6';
  sec.innerHTML = [
    '<div class="bg-surface border border-slate-800 rounded-xl p-4 space-y-3">',
    '  <h3 class="text-sm font-bold text-white"><i class="fa-solid fa-screwdriver-wrench mr-2 text-blue-400"></i>Maintenance</h3>',
    '  <div class="grid grid-cols-1 sm:grid-cols-3 gap-2 items-center">',
    '    <select id="mxOn" class="' + SEL + '"><option value="0">Site normal</option><option value="1">Recherche desactivee</option></select>',
    '    <a href="/" target="_blank" class="text-[11px] text-slate-400 hover:text-white underline">voir la page publique</a>',
    '    <button id="mxSave" class="px-3 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-semibold">Appliquer</button>',
    '  </div>',
    '  <textarea id="mxText" rows="2" class="w-full bg-dark border border-slate-800 rounded-lg p-3 text-[11px] text-slate-200"></textarea>',
    '  <p class="text-[10px] text-slate-500">Bypass admin : <code>/?bypass=&lt;ADMIN_TOKEN&gt;</code> pour voir le vrai site pendant la maintenance.</p>',
    '</div>',

    '<div class="bg-surface border border-slate-800 rounded-xl p-4 space-y-3">',
    '  <h3 class="text-sm font-bold text-white"><i class="fa-solid fa-plus mr-2 text-amber-400"></i>Ajouter / modifier une regle</h3>',
    '  <div class="grid grid-cols-1 sm:grid-cols-3 gap-2">',
    '    <select id="arScope" class="' + SEL + '">',
    '      <option value="ip">Par IP</option><option value="key">Par cle API</option><option value="user">Par utilisateur</option>',
    '    </select>',
    '    <select id="arIdent" class="' + SEL + ' sm:col-span-2"></select>',
    '    <select id="arExpire" class="' + SEL + '"></select>',
    '    <select id="arBlocked" class="' + SEL + '"><option value="0">Autorise (avec perimetre)</option><option value="1">Bloque completement</option></select>',
    '    <select id="arCible" class="' + SEL + '"><option value="les_deux">Perimetre : web + API</option><option value="web">Perimetre : web uniquement</option><option value="api">Perimetre : API uniquement</option></select>',
    '    <input id="arNote" placeholder="note (optionnel)" class="bg-dark border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200">',
    '  </div>',
    '  <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">',
    '    <div><div class="text-[10px] uppercase text-slate-500 mb-1">Routes autorisees (aucune cochee = toutes)</div>',
    '      <div id="arAllow" class="bg-dark border border-slate-800 rounded-lg p-2 max-h-40 overflow-auto space-y-1"></div></div>',
    '    <div><div class="text-[10px] uppercase text-slate-500 mb-1">Routes refusees</div>',
    '      <div id="arDeny" class="bg-dark border border-slate-800 rounded-lg p-2 max-h-40 overflow-auto space-y-1"></div></div>',
    '  </div>',
    '  <div class="flex items-center gap-3">',
    '    <button id="arSave" class="px-4 py-2 bg-amber-600 hover:bg-amber-500 text-white rounded-lg text-xs font-semibold">Enregistrer</button>',
    '    <button id="arReset" class="px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs">Vider</button>',
    '    <span id="arMsg" class="text-[11px] text-slate-400"></span>',
    '  </div>',
    '  <p class="text-[10px] text-slate-500">Priorite : cle &gt; utilisateur &gt; IP. Blocage en OU. /static et /admin exemptes.</p>',
    '</div>',

    '<div class="bg-surface border border-slate-800 rounded-xl p-4 space-y-3">',
    '  <h3 class="text-sm font-bold text-white"><i class="fa-solid fa-vial mr-2 text-emerald-400"></i>Simulateur</h3>',
    '  <div class="grid grid-cols-1 sm:grid-cols-4 gap-2">',
    '    <select id="tsScope" class="' + SEL + '"><option value="ip">Par IP</option><option value="key">Par cle API</option><option value="user">Par utilisateur</option></select>',
    '    <select id="tsIdent" class="' + SEL + ' sm:col-span-2"></select>',
    '    <select id="tsPath" class="' + SEL + '"></select>',
    '  </div>',
    '  <button id="tsGo" class="px-3 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-semibold">Tester</button>',
    '  <pre id="tsOut" class="bg-dark border border-slate-800 rounded-lg p-3 text-[11px] text-slate-300"></pre>',
    '</div>',

    '<div class="bg-surface border border-slate-800 rounded-xl overflow-hidden">',
    '  <table class="w-full text-left text-xs"><thead class="bg-dark/60 text-slate-400 font-mono text-[11px]">',
    '    <tr><th class="py-2.5 px-3">Portee</th><th class="px-3">Identifiant</th><th class="px-3">Etat</th><th class="px-3">Autorise</th><th class="px-3">Refuse</th><th class="px-3">Note</th><th class="px-3"></th></tr>',
    '  </thead><tbody id="arRows" class="divide-y divide-slate-800/60"></tbody></table>',
    '</div>'
  ].join('\n');
  hote.parentElement.appendChild(sec);

  var orig = window.switchMainTab;
  window.switchMainTab = function (tab) {
    if (tab === 'access') {
      ['tabContentKeys', 'tabContentUsers', 'tabContentPricing', 'tabContentWebAccess'].forEach(function (id) {
        var e = document.getElementById(id); if (e) e.classList.add('hidden');
      });
      ['tabBtnKeys', 'tabBtnUsers', 'tabBtnPricing', 'tabBtnWebAccess'].forEach(function (id) {
        var e = document.getElementById(id); if (e) e.className = IDLE;
      });
      sec.classList.remove('hidden');
      btn.className = ACTIF;
      window.arLoad();
      mxLoad();
      return;
    }
    sec.classList.add('hidden');
    btn.className = IDLE;
    if (orig) orig(tab);
  };

  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function opts(sel, valeurs, vide) {
    sel.innerHTML = (vide ? '<option value="">' + vide + '</option>' : '') +
      valeurs.map(function (v) { return '<option value="' + esc(v) + '">' + esc(v) + '</option>'; }).join('');
  }
  function optsObjets(sel, valeurs) {
    sel.innerHTML = valeurs.map(function (o) { return '<option value="' + esc(o.id) + '">' + esc(o.label) + '</option>'; }).join('');
  }

  var CHOIX = { ips: [], keys: [], users: [], routes: [] };



  function lireListe(prefixe) {
    return Array.prototype.slice.call(document.querySelectorAll('.' + prefixe + ':checked'))
      .filter(function (c) { return c.getAttribute('data-r'); })
      .map(function (c) { return c.getAttribute('data-r'); });
  }
  function lireCases(prefixe) { return lireListe(prefixe).join(','); }

  function cocher(prefixe, valeur) {
    var liste = String(valeur || '').split(',').map(function (s) { return s.trim(); }).filter(Boolean);
    document.querySelectorAll('.' + prefixe).forEach(function (c) {
      c.checked = liste.indexOf(c.getAttribute('data-r')) !== -1;
    });
  }


  var GROUPES = [], PAIRES = {};

  async function chargerRoutes() {
    var r = await fetch('/admin/api/access-rules/routes');
    if (!r.ok) return;
    var d = await r.json();
    GROUPES = d.groupes || [];
    PAIRES = d.paires || {};
    rendreCases(document.getElementById('arAllow'), 'chk-allow');
    rendreCases(document.getElementById('arDeny'), 'chk-deny');
    opts(document.getElementById('tsPath'),
         GROUPES.reduce(function (a, g) { return a.concat(g.routes); }, []), null);
  }

  function rendreCases(conteneur, prefixe) {
    conteneur.innerHTML = GROUPES.map(function (g) {
      return '<div class="mb-2">' +
        '<label class="flex items-center gap-2 text-[10px] uppercase tracking-wide text-slate-500 mb-1 cursor-pointer">' +
        '<input type="checkbox" class="accent-amber-500 ' + prefixe + '-grp" data-grp="' + esc(g.nom) + '"> ' + esc(g.nom) + '</label>' +
        g.routes.map(function (r) {
          return '<label class="flex items-center gap-2 text-[11px] text-slate-300 ml-3">' +
            '<input type="checkbox" data-r="' + esc(r) + '" class="accent-amber-500 ' + prefixe + '">' +
            '<span class="font-mono">' + esc(r) + '</span></label>';
        }).join('') + '</div>';
    }).join('') || '<span class="text-[11px] text-slate-500">aucune route</span>';

    conteneur.querySelectorAll('.' + prefixe + '-grp').forEach(function (grp) {
      grp.onchange = function () {
        var nom = grp.getAttribute('data-grp');
        var g = GROUPES.filter(function (x) { return x.nom === nom; })[0];
        if (!g) return;
        g.routes.forEach(function (r) {
          var cb = conteneur.querySelector('input[data-r="' + r + '"]');
          if (cb) cb.checked = grp.checked;
        });
      };
    });
  }

  function etendre(routes, cible) {
    var out = {};
    routes.forEach(function (r) {
      if (cible === 'les_deux') {
        out[r] = 1;
        if (PAIRES[r]) out[PAIRES[r]] = 1;
      } else if (cible === 'web' && r.indexOf('/api/') === 0) {
        out[r] = 1;
      } else if (cible === 'api' && r.indexOf('/v1/') === 0) {
        out[r] = 1;
      }
    });
    return Object.keys(out).join(',');
  }

  async function chargerChoix() {
    var r = await fetch('/admin/api/access-rules/choices');
    if (!r.ok) return;
    var d = await r.json();
    CHOIX = Object.assign({ ips: [], keys: [], users: [], expirations: [] }, d);
    opts(document.getElementById('arExpire'), CHOIX.expirations || [], 'expiration : jamais');
    await chargerRoutes();
    majIdent('arScope', 'arIdent');
    majIdent('tsScope', 'tsIdent');
  }

  function majIdent(selScope, selIdent) {
    var portee = document.getElementById(selScope).value;
    var cible = document.getElementById(selIdent);
    if (portee === 'ip') opts(cible, CHOIX.ips || [], 'choisir une IP');
    else if (portee === 'key') optsObjets(cible, CHOIX.keys || []);
    else optsObjets(cible, CHOIX.users || []);
  }

  document.getElementById('arScope').onchange = function () { majIdent('arScope', 'arIdent'); };
  document.getElementById('tsScope').onchange = function () { majIdent('tsScope', 'tsIdent'); };

  window.arLoad = async function () {
   try {
    if (!GROUPES.length) await chargerChoix();
    var res = await fetch('/admin/api/access-rules');
    var data = await res.json();
    document.getElementById('arRows').innerHTML = (data.items || []).map(function (r) {
      return '<tr>' +
        '<td class="py-2 px-3 text-slate-400">' + esc(r.scope) + '</td>' +
        '<td class="px-3 font-mono text-slate-200">' + esc(r.ident) + '</td>' +
        '<td class="px-3">' + (r.is_blocked ? '<span class="text-red-400">bloque</span>' : '<span class="text-emerald-400">ok</span>') + '</td>' +
        '<td class="px-3 text-slate-400 font-mono text-[11px]">' + esc(r.allow_routes || '-') + '</td>' +
        '<td class="px-3 text-slate-400 font-mono text-[11px]">' + esc(r.deny_routes || '-') + '</td>' +
        '<td class="px-3 text-slate-500">' + esc(r.note || '') + '</td>' +
        '<td class="px-3"><button class="text-red-400 hover:text-red-300" onclick="arDel(\'' + esc(r.scope) + '\',\'' + esc(r.ident) + '\')">supprimer</button></td>' +
        '</tr>';
    }).join('') || '<tr><td colspan="7" class="py-3 px-3 text-slate-500">Aucune regle</td></tr>';
   } catch (e) { console.error('[access]', e); }
  };

  window.arDel = async function (scope, ident) {
    var msg = document.getElementById('arMsg');
    try {
      var r = await fetch('/admin/api/access-rules/' + encodeURIComponent(scope) + '/' + encodeURIComponent(ident),
                          { method: 'DELETE' });
      if (msg) msg.textContent = r.ok ? 'regle supprimee' : 'erreur suppression';
    } catch (e) {
      if (msg) msg.textContent = 'erreur reseau';
    }
    try { await window.arLoad(); } catch (e) { console.error('[access]', e); }
  };

  document.getElementById('arReset').onclick = function () {
    document.getElementById('arNote').value = '';
    document.getElementById('arBlocked').value = '0';
    document.getElementById('arExpire').value = '';
    cocher('chk-allow', ''); cocher('chk-deny', '');
    document.getElementById('arMsg').textContent = '';
  };

  document.getElementById('arSave').onclick = async function () {
    var ident = document.getElementById('arIdent').value;
    if (!ident) { document.getElementById('arMsg').textContent = 'choisis un identifiant'; return; }
    var exp = document.getElementById('arExpire').value;
    var delais = { '1 heure': 1, '24 heures': 24, '7 jours': 168, '30 jours': 720 };
    var expires_at = null;
    if (delais[exp]) {
      var d = new Date(Date.now() + delais[exp] * 3600 * 1000);
      expires_at = d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0') +
                   ' ' + String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0') + ':00';
    }
    var body = {
      scope: document.getElementById('arScope').value,
      ident: ident,
      is_blocked: parseInt(document.getElementById('arBlocked').value, 10),
      allow_routes: etendre(lireListe('chk-allow'), document.getElementById('arCible').value),
      deny_routes: etendre(lireListe('chk-deny'), document.getElementById('arCible').value),
      note: document.getElementById('arNote').value.trim(),
      expires_at: expires_at
    };
    var r = await fetch('/admin/api/access-rules', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body)
    });
    document.getElementById('arMsg').textContent = r.ok ? 'enregistre' : 'erreur';
    window.arLoad();
  };

  document.getElementById('tsGo').onclick = async function () {
    var portee = document.getElementById('tsScope').value;
    var ident = document.getElementById('tsIdent').value;
    var corps = { path: document.getElementById('tsPath').value || '/' };
    if (portee === 'ip') corps.ip = ident;
    else if (portee === 'key') corps.key_id = ident;
    else corps.user_id = ident;
    var r = await fetch('/admin/api/access-rules/test', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(corps)
    });
    document.getElementById('tsOut').textContent = JSON.stringify(await r.json(), null, 2);
  };

  async function mxLoad() {
    try {
      var r = await fetch('/api/config', { cache: 'no-store' });
      var c = await r.json();
      document.getElementById('mxOn').value = c.maintenance_mode ? '1' : '0';
      document.getElementById('mxText').value = c.maintenance_text || '';
    } catch (e) {}
  }
  document.getElementById('mxSave').onclick = async function () {
    var r = await fetch('/admin/api/settings', {
      method: 'PATCH', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ values: {
        maintenance_mode: document.getElementById('mxOn').value,
        maintenance_text: document.getElementById('mxText').value
      } })
    });
    document.getElementById('mxMsg').textContent = r.ok ? 'applique' : 'erreur';
  };
})();
