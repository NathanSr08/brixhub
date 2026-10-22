/* =====================================================================
   BrixHub - Extensions de l'onglet Logs Globaux
   Ajoute : tag "Clic profil", fiche consultee, profils consultes par
   acteur, top profils, et la purge des logs (filtres / mois / tout).
   Charge APRES logs.js
   ===================================================================== */
(function () {
    'use strict';

    var _esc = window._esc || function (v) {
        return String(v === null || v === undefined ? '' : v)
            .replace(/[&<>"']/g, function (c) {
                return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
            });
    };
    var _ts = window._ts || function (v) { return v || '-'; };

    /* ---------------- modales additionnelles ---------------- */
    var EXTRA_MODALS = `
<div id="profileModal" class="hidden fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
  <div class="bg-surface border border-slate-800 rounded-2xl w-full max-w-3xl max-h-[88vh] overflow-y-auto custom-scroll">
    <div class="flex items-center justify-between p-4 border-b border-slate-800">
      <h3 class="text-sm font-bold text-white"><i class="fa-solid fa-address-card mr-2 text-emerald-400"></i>Fiche consultee</h3>
      <button onclick="document.getElementById('profileModal').classList.add('hidden')" class="text-slate-400 hover:text-white"><i class="fa-solid fa-xmark"></i></button>
    </div>
    <div id="profileBody" class="p-4 space-y-4 text-xs"></div>
  </div>
</div>
<div id="purgeModal" class="hidden fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
  <div class="bg-surface border border-slate-800 rounded-2xl w-full max-w-2xl max-h-[88vh] overflow-y-auto custom-scroll">
    <div class="flex items-center justify-between p-4 border-b border-slate-800">
      <h3 class="text-sm font-bold text-white"><i class="fa-solid fa-broom mr-2 text-amber-400"></i>Purger les logs</h3>
      <button onclick="document.getElementById('purgeModal').classList.add('hidden')" class="text-slate-400 hover:text-white"><i class="fa-solid fa-xmark"></i></button>
    </div>
    <div id="purgeBody" class="p-4 space-y-4 text-xs"></div>
  </div>
</div>`;

    /* ---------------- helpers ---------------- */
    function currentFilters() {
        var p = window.logParams ? window.logParams(0) : new URLSearchParams();
        var o = {};
        p.forEach(function (v, k) { if (k !== 'limit' && k !== 'offset') o[k] = v; });
        return o;
    }

    function targetNames() {
        var out = [];
        if (document.getElementById('pgAudit').checked) out.push('audit');
        if (document.getElementById('pgClicks').checked) out.push('clicks');
        if (document.getElementById('pgActions').checked) out.push('admin_actions');
        return out;
    }

    function mode() {
        var r = document.querySelector('input[name="pgMode"]:checked');
        return r ? r.value : 'filter';
    }

    /* ---------------- fiche consultee ---------------- */
    window.openProfileCard = async function (ref) {
        var body = document.getElementById('profileBody');
        body.innerHTML = '<div class="text-slate-400">Chargement...</div>';
        document.getElementById('profileModal').classList.remove('hidden');
        try {
            var res = await fetch('/admin/api/profiles/' + encodeURIComponent(ref));
            if (!res.ok) { body.innerHTML = '<div class="text-red-400">Fiche introuvable</div>'; return; }
            var p = await res.json();
            var f = p.fiche || {};
            function row(k, v) {
                return '<div class="flex gap-3 border-b border-slate-800/60 py-1.5"><span class="w-36 shrink-0 text-slate-500">' + k +
                    '</span><span class="flex-1 break-all text-slate-200">' + _esc(v || '-') + '</span></div>';
            }
            body.innerHTML =
                '<div class="flex flex-wrap gap-2 items-center"><span class="px-2 py-0.5 rounded-md text-[10px] font-bold bg-emerald-600/20 text-emerald-300 border border-emerald-700/40">FICHE</span>' +
                '<span class="font-mono text-[11px] text-slate-400">' + _esc(ref) + '</span></div>' +
                '<div class="grid md:grid-cols-2 gap-4"><div><div class="text-slate-500 mb-1">Identite</div>' +
                row('Nom Prenom', (f.nom || '') + ' ' + (f.prenom || '')) + row('Naissance', f.date_naissance) +
                row('Ville', f.ville) + row('Code postal', f.code_postal) + row('Mail', f.mail) +
                row('Telephone', f.tel) + row('Source', f.source) + '</div>' +
                '<div><div class="text-slate-500 mb-1">Consultations</div>' + row('Total clics', p.total_clicks) +
                row('Acteurs uniques', p.acteurs_uniques) + row('IP uniques', p.ips_uniques) +
                row('Premier', _ts(p.premier)) + row('Dernier', _ts(p.dernier)) +
                row('Par user / guest / api', p.par_users + ' / ' + p.par_guests + ' / ' + p.par_api) + '</div></div>' +
                '<div><div class="text-slate-500 mb-1">Qui a consulte</div><div class="space-y-1">' +
                ((p.acteurs || []).map(function (a) {
                    return '<div class="flex items-center gap-2 font-mono text-[11px]"><span class="px-1.5 py-0.5 rounded bg-slate-800 text-slate-300">' +
                        _esc(a.actor_type) + '</span><button onclick="openActor(\'' + a.actor_type + '\',\'' + a.actor_id + '\')" class="text-indigo-300 hover:underline truncate">' +
                        _esc(a.actor_label || a.actor_id) + '</button><span class="text-slate-500 ml-auto">' + a.clicks + 'x</span><span class="text-slate-600">' + _ts(a.dernier) + '</span></div>';
                }).join('') || '-') + '</div></div>' +
                '<div><div class="text-slate-500 mb-1">Criteres de recherche ayant mene a cette fiche</div><div class="space-y-1">' +
                ((p.criteres || []).map(function (c) {
                    return '<div class="flex justify-between font-mono text-[11px]"><span class="text-emerald-300 truncate">' + _esc(c.criteria) + '</span><span class="text-slate-500">' + c.n + '</span></div>';
                }).join('') || '-') + '</div></div>';
        } catch (e) { body.innerHTML = '<div class="text-red-400">Erreur</div>'; }
    };

    /* ---------------- detail d'un log clic ---------------- */
    var _origDetail = window.openLogDetail;
    window.openLogDetail = function (i) {
        if (typeof _origDetail === 'function') _origDetail(i);
        var l = window.allLogs && window.allLogs[i];
        if (!l || l.tag !== 'click') return;
        var m = {};
        try { m = JSON.parse(l.meta || '{}'); } catch (e) { }
        var body = document.getElementById('logDetailBody');
        if (!body) return;
        var block = document.createElement('div');
        block.className = 'mt-4 p-3 rounded-xl bg-emerald-600/10 border border-emerald-800/40';
        block.innerHTML =
            '<div class="text-emerald-300 font-bold mb-2"><i class="fa-solid fa-user-check mr-2"></i>Fiche consultee</div>' +
            '<div class="grid grid-cols-2 gap-x-4 gap-y-1 text-[11px] text-slate-300">' +
            '<div><span class="text-slate-500">Nom :</span> ' + _esc(m.profil) + '</div>' +
            '<div><span class="text-slate-500">Naissance :</span> ' + _esc(m.date_naissance) + '</div>' +
            '<div><span class="text-slate-500">Ville :</span> ' + _esc(m.ville) + '</div>' +
            '<div><span class="text-slate-500">CP :</span> ' + _esc(m.code_postal) + '</div>' +
            '<div><span class="text-slate-500">Mail :</span> ' + _esc(m.mail) + '</div>' +
            '<div><span class="text-slate-500">Tel :</span> ' + _esc(m.tel) + '</div>' +
            '<div><span class="text-slate-500">Source :</span> ' + _esc(m.source) + '</div>' +
            '<div><span class="text-slate-500">Rang :</span> ' + _esc(m.rank) + ' / ' + _esc(m.result_count) + '</div>' +
            '<div class="col-span-2"><span class="text-slate-500">Criteres :</span> ' + _esc(m.criteria) + '</div>' +
            '</div>' +
            '<button onclick="openProfileCard(\'' + (m.profile_ref || '') + '\')" class="mt-3 px-3 py-1.5 rounded-lg bg-emerald-600 text-white text-[11px] font-semibold">' +
            '<i class="fa-solid fa-users-viewfinder mr-1"></i>Qui a consulte cette fiche</button>';
        body.appendChild(block);
    };

    /* ---------------- profils consultes par acteur ---------------- */
    var _origActor = window.openActor;
    window.openActor = async function (type, id) {
        if (typeof _origActor === 'function') await _origActor(type, id);
        var body = document.getElementById('actorBody');
        if (!body) return;
        var zone = document.createElement('div');
        zone.id = 'actorClicksZone';
        zone.innerHTML = '<div class="text-slate-500">Chargement des fiches consultees...</div>';
        body.appendChild(zone);
        try {
            var res = await fetch('/admin/api/clicks/actor/' + encodeURIComponent(type) + '/' + encodeURIComponent(id) + '?limit=30');
            if (!res.ok) { zone.innerHTML = ''; return; }
            var list = await res.json();
            zone.innerHTML = '<div class="text-slate-500 mb-1">Fiches consultees (' + list.length + ')</div>' +
                '<div class="space-y-1 max-h-52 overflow-y-auto custom-scroll font-mono text-[11px]">' +
                (list.map(function (c) {
                    return '<div class="flex items-center gap-2"><span class="text-slate-500">' + _ts(c.ts) + '</span>' +
                        '<button onclick="openProfileCard(\'' + c.profile_ref + '\')" class="text-emerald-300 hover:underline truncate">' +
                        _esc((c.nom || '') + ' ' + (c.prenom || '')) + '</button>' +
                        '<span class="text-slate-500">' + _esc(c.ville) + '</span>' +
                        '<span class="text-slate-600 ml-auto">#' + c.rang + '</span></div>';
                }).join('') || '-') + '</div>';
        } catch (e) { zone.innerHTML = ''; }
    };

    /* ---------------- colonne Endpoint pour les clics ---------------- */
    var _origRender = window.renderLogs;
    window.renderLogs = function () {
        if (typeof _origRender === 'function') _origRender();
        var trs = document.querySelectorAll('#logsTableBody tr');
        for (var i = 0; i < trs.length; i++) {
            var l = window.allLogs && window.allLogs[i];
            if (!l || l.tag !== 'click') continue;
            var m = {};
            try { m = JSON.parse(l.meta || '{}'); } catch (e) { }
            var cell = trs[i].children[4];
            if (cell) {
                cell.innerHTML = '<span class="text-emerald-300"><i class="fa-solid fa-user-check mr-1"></i>' +
                    _esc(m.profil || 'fiche') + '</span>' +
                    (m.ville ? '<div class="text-[10px] text-slate-500">' + _esc(m.ville) +
                        (m.source ? ' / ' + _esc(m.source) : '') + '</div>' : '');
            }
        }
    };

    /* ---------------- top profils ---------------- */
    window.openTopProfiles = async function () {
        var body = document.getElementById('profileBody');
        body.innerHTML = '<div class="text-slate-400">Chargement...</div>';
        document.getElementById('profileModal').classList.remove('hidden');
        try {
            var res = await fetch('/admin/api/clicks/stats?hours=720');
            var s = await res.json();
            body.innerHTML =
                '<div class="grid grid-cols-3 gap-3 mb-2">' +
                '<div class="bg-dark border border-slate-800 rounded-xl p-3"><div class="text-slate-500 text-[10px]">Clics (30j)</div><div class="text-xl font-extrabold text-white">' + s.total + '</div></div>' +
                '<div class="bg-dark border border-slate-800 rounded-xl p-3"><div class="text-slate-500 text-[10px]">Fiches distinctes</div><div class="text-xl font-extrabold text-emerald-300">' + s.profils_uniques + '</div></div>' +
                '<div class="bg-dark border border-slate-800 rounded-xl p-3"><div class="text-slate-500 text-[10px]">Acteurs distincts</div><div class="text-xl font-extrabold text-indigo-300">' + s.acteurs_uniques + '</div></div>' +
                '</div>' +
                '<div class="text-slate-500 mb-1">Fiches les plus consultees</div><div class="space-y-1">' +
                ((s.top_profils || []).map(function (p) {
                    return '<div class="flex items-center gap-2 font-mono text-[11px]"><button onclick="openProfileCard(\'' + p.profile_ref + '\')" class="text-emerald-300 hover:underline truncate">' +
                        _esc((p.nom || '') + ' ' + (p.prenom || '')) + '</button><span class="text-slate-500">' + _esc(p.ville) + '</span><span class="text-slate-600">' + _esc(p.source) + '</span><span class="text-slate-400 ml-auto">' + p.clicks + 'x</span></div>';
                }).join('') || '-') + '</div>' +
                '<div class="text-slate-500 mt-4 mb-1">Acteurs qui consultent le plus</div><div class="space-y-1">' +
                ((s.top_acteurs || []).map(function (a) {
                    return '<div class="flex items-center gap-2 font-mono text-[11px]"><span class="px-1.5 py-0.5 rounded bg-slate-800 text-slate-300">' + _esc(a.actor_type) + '</span>' +
                        '<button onclick="openActor(\'' + a.actor_type + '\',\'' + a.actor_id + '\')" class="text-indigo-300 hover:underline truncate">' + _esc(a.actor_label || a.actor_id) + '</button>' +
                        '<span class="text-slate-400 ml-auto">' + a.clicks + 'x</span></div>';
                }).join('') || '-') + '</div>';
        } catch (e) { body.innerHTML = '<div class="text-red-400">Erreur</div>'; }
    };

    /* ---------------- purge ---------------- */
    window.openPurge = async function () {
        document.getElementById('purgeModal').classList.remove('hidden');
        await purgePreview();
    };

    window.purgePreview = async function () {
        var body = document.getElementById('purgeBody');
        var targets = targetNames();
        if (!targets.length) { body.innerHTML = '<div class="text-amber-400">Choisis au moins une cible.</div>'; return; }
        body.innerHTML = '<div class="text-slate-400">Calcul...</div>';
        try {
            var res = await fetch('/admin/api/logs/purge/preview', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ targets: targets, mode: mode(), filters: currentFilters(), partitions: selectedPartitions() })
            });
            var d = await res.json();
            var html = '';
            (d.targets || []).forEach(function (t) {
                html += '<div class="bg-dark border border-slate-800 rounded-xl p-3">' +
                    '<div class="font-mono text-[11px] text-slate-300">' + _esc(t.target) + '</div>' +
                    '<div class="text-slate-500 text-[11px]">Total : ' + t.lignes + ' lignes / ' + t.taille + '</div>' +
                    '<div class="text-amber-300 font-bold text-[11px]">A supprimer : ' + t.a_supprimer + ' lignes</div>' +
                    (t.condition ? '<div class="text-slate-600 text-[10px] break-all mt-1">' + _esc(t.condition) + '</div>' : '') +
                    '</div>';
                if (t.partitions && t.partitions.length && mode() === 'partitions') {
                    html += '<div class="space-y-1 mt-1">' + t.partitions.map(function (p) {
                        var on = selectedPartitions().indexOf(p.partition) !== -1;
                        return '<label class="flex items-center gap-2 font-mono text-[11px]"><input type="checkbox" class="pgPart" value="' + p.partition + '" onchange="purgePreview()" ' + (on ? 'checked' : '') + '>' +
                            '<span class="text-slate-300">' + p.partition + '</span><span class="text-slate-500">' + p.lignes + ' lignes / ' + p.taille + '</span></label>';
                    }).join('') + '</div>';
                }
            });
            body.innerHTML = html;
        } catch (e) { body.innerHTML = '<div class="text-red-400">Erreur de calcul</div>'; }
    };

    function selectedPartitions() {
        var out = [];
        document.querySelectorAll('.pgPart').forEach(function (c) { if (c.checked) out.push(c.value); });
        return out;
    }

    window.runPurge = async function () {
        var targets = targetNames();
        if (!targets.length) return;
        var m = mode();
        if (m === 'all' && !confirm('TRUNCATE : tout supprimer sur ' + targets.join(', ') + ' ?')) return;
        var body = document.getElementById('purgeBody');
        body.innerHTML = '<div class="text-slate-400">Suppression en cours (peut prendre plusieurs secondes)...</div>';
        try {
            var res = await fetch('/admin/api/logs/purge', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ targets: targets, mode: m, filters: currentFilters(), partitions: selectedPartitions() })
            });
            var d = await res.json();
            body.innerHTML = '<div class="text-emerald-400 font-bold">Purge terminee.</div>' +
                '<pre class="bg-dark border border-slate-800 rounded-lg p-3 text-[11px] text-slate-300 overflow-x-auto">' +
                _esc(JSON.stringify(d.done, null, 2)) + '</pre>' +
                '<div class="text-slate-500 mt-2">Les mutations ClickHouse sont synchrones ; le disque est libere apres fusion.</div>';
            if (window.fetchLogs) window.fetchLogs();
            if (window.fetchLogsStats) window.fetchLogsStats();
        } catch (e) { body.innerHTML = '<div class="text-red-400">Erreur pendant la purge</div>'; }
    };

    window.runOptimize = async function () {
        var body = document.getElementById('purgeBody');
        body.innerHTML = '<div class="text-slate-400">Optimisation (fusion des parts)...</div>';
        try {
            await fetch('/admin/api/logs/optimize', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ targets: targetNames() })
            });
            body.innerHTML = '<div class="text-emerald-400">Optimisation lancee.</div>';
        } catch (e) { body.innerHTML = '<div class="text-red-400">Erreur</div>'; }
    };

    window.purgeExport = function () {
        window.open('/admin/api/logs/export.csv?' + currentFilters2QS(), '_blank');
    };
    function currentFilters2QS() {
        var p = window.logParams ? window.logParams(0) : new URLSearchParams();
        return p.toString();
    }

    /* ---------------- injection dans la barre d'outils ---------------- */
    function inject() {
        var tag = document.getElementById('logTag');
        if (tag && !tag.querySelector('option[value="click"]')) {
            var o = document.createElement('option');
            o.value = 'click';
            o.textContent = 'Clic profil';
            tag.appendChild(o);
        }
        var bar = document.getElementById('logLiveBtn');
        if (!bar || document.getElementById('btnTopProfiles')) return;

        var b1 = document.createElement('button');
        b1.id = 'btnTopProfiles';
        b1.setAttribute('onclick', 'openTopProfiles()');
        b1.className = 'px-3 py-2 rounded-lg text-xs font-semibold bg-emerald-700 text-white border border-emerald-600';
        b1.innerHTML = '<i class="fa-solid fa-users-viewfinder"></i> Profils consultes';
        bar.insertAdjacentElement('beforebegin', b1);

        var b2 = document.createElement('button');
        b2.id = 'btnPurge';
        b2.setAttribute('onclick', 'openPurge()');
        b2.className = 'px-3 py-2 rounded-lg text-xs font-semibold bg-amber-600 text-white border border-amber-500';
        b2.innerHTML = '<i class="fa-solid fa-broom"></i> Purger';
        bar.insertAdjacentElement('beforebegin', b2);

        var host = document.getElementById('tabContentLogs') || document.body;
        var wrap = document.createElement('div');
        wrap.innerHTML = EXTRA_MODALS;
        while (wrap.firstChild) host.appendChild(wrap.firstChild);

        var body = document.getElementById('purgeBody');
        if (body) {
            body.innerHTML = `
<div class="space-y-3">
  <div>
    <div class="text-slate-400 mb-1">Cibles</div>
    <div class="flex flex-wrap gap-3">
      <label class="flex items-center gap-1.5"><input type="checkbox" id="pgAudit" checked onchange="purgePreview()"> Logs d'audit</label>
      <label class="flex items-center gap-1.5"><input type="checkbox" id="pgClicks" onchange="purgePreview()"> Clics sur fiches</label>
      <label class="flex items-center gap-1.5"><input type="checkbox" id="pgActions" onchange="purgePreview()"> Actions admin</label>
    </div>
  </div>
  <div>
    <div class="text-slate-400 mb-1">Portee</div>
    <div class="flex flex-wrap gap-3">
      <label class="flex items-center gap-1.5"><input type="radio" name="pgMode" value="filter" checked onchange="purgePreview()"> Filtres actuels de la liste</label>
      <label class="flex items-center gap-1.5"><input type="radio" name="pgMode" value="partitions" onchange="purgePreview()"> Par mois (partitions)</label>
      <label class="flex items-center gap-1.5"><input type="radio" name="pgMode" value="all" onchange="purgePreview()"> Tout (TRUNCATE)</label>
    </div>
  </div>
  <div class="flex flex-wrap gap-2">
    <button onclick="purgeExport()" class="px-3 py-2 rounded-lg bg-slate-800 border border-slate-700 text-slate-200 text-[11px] font-semibold"><i class="fa-solid fa-file-csv mr-1"></i>Exporter d'abord en CSV</button>
    <button onclick="purgePreview()" class="px-3 py-2 rounded-lg bg-slate-800 border border-slate-700 text-slate-200 text-[11px] font-semibold"><i class="fa-solid fa-calculator mr-1"></i>Recalculer</button>
    <button onclick="runOptimize()" class="px-3 py-2 rounded-lg bg-slate-800 border border-slate-700 text-slate-200 text-[11px] font-semibold"><i class="fa-solid fa-compress mr-1"></i>Optimiser (liberer le disque)</button>
    <button onclick="runPurge()" class="px-3 py-2 rounded-lg bg-red-600 text-white text-[11px] font-semibold"><i class="fa-solid fa-trash mr-1"></i>Supprimer</button>
  </div>
</div>
<div id="purgePreviewZone" class="mt-3"></div>`;
            var zone = document.getElementById('purgePreviewZone');
            zone.id = 'purgeBody';
            body.id = 'purgePreviewInner';
        }
    }

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', inject);
    else inject();
})();
