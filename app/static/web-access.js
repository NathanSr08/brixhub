/* BrixHub - Onglet "Acces Web" : illimite / quota par utilisateur */
(function () {
  if (document.getElementById('tabBtnWebAccess')) return;
  var ref = document.getElementById('tabBtnUsers');
  var host = document.getElementById('tabContentUsers');
  if (!ref || !host) return;
  var IDLE = "px-4 py-2 rounded-xl bg-surface hover:bg-slate-800 text-slate-400 hover:text-white transition flex items-center gap-2 border border-slate-800";
  var ACTIVE = "px-4 py-2 rounded-xl bg-fuchsia-600 text-white transition flex items-center gap-2";

  var btn = document.createElement('button');
  btn.id = 'tabBtnWebAccess';
  btn.className = IDLE;
  btn.innerHTML = '<i class="fa-solid fa-shield-halved"></i> <span>Acces Web</span>';
  btn.onclick = function () { window.switchMainTab('web'); };
  ref.insertAdjacentElement('afterend', btn);

  var sec = document.createElement('div');
  sec.id = 'tabContentWebAccess';
  sec.className = 'hidden space-y-6';
  sec.innerHTML = [
    '<div class="bg-surface border border-slate-800 rounded-xl p-4 flex flex-wrap items-center gap-3">',
    '  <div><div class="text-[10px] uppercase tracking-wide text-slate-500">Regle globale</div>',
    '  <div class="text-xs text-slate-300">Tout compte possedant une cle API est illimite sur le web</div></div>',
    '  <label class="ml-auto flex items-center gap-2 text-xs text-slate-300">',
    '    <input type="checkbox" id="waGlobal" class="accent-fuchsia-500"> <span id="waGlobalMsg">...</span></label>',
    '</div>',
    '<div class="bg-surface border border-slate-800 rounded-xl p-4 space-y-3">',
    '  <div class="flex gap-2">',
    '    <input id="waSearch" placeholder="email ou user_id..." class="flex-1 bg-dark border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200">',
    '    <button id="waReload" class="px-3 py-2 bg-fuchsia-600 hover:bg-fuchsia-500 text-white rounded-lg text-xs font-semibold">Chercher</button>',
    '  </div>',
    '  <div class="text-[10px] text-slate-500">Quota vide = suit le plan. Quota 0 = illimite. Priorite : illimite force &gt; cle API &gt; quota specifique &gt; plan.</div>',
    '  <div id="waTable" class="space-y-2"></div>',
    '</div>'
  ].join('\n');
  host.parentElement.appendChild(sec);

  var orig = window.switchMainTab;
  window.switchMainTab = function (tab) {
    if (tab === 'web') {
      ['tabContentKeys', 'tabContentUsers', 'tabContentPricing'].forEach(function (id) {
        var e = document.getElementById(id); if (e) e.classList.add('hidden');
      });
      ['tabBtnKeys', 'tabBtnUsers', 'tabBtnPricing'].forEach(function (id) {
        var e = document.getElementById(id); if (e) e.className = IDLE;
      });
      sec.classList.remove('hidden');
      btn.className = ACTIVE;
      window.waLoad();
      return;
    }
    sec.classList.add('hidden');
    btn.className = IDLE;
    if (orig) orig(tab);
  };

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }

  window.waLoad = async function () {
    var q = (document.getElementById('waSearch').value || '').trim();
    var res = await fetch('/admin/api/web-users?q=' + encodeURIComponent(q));
    if (!res.ok) {
      document.getElementById('waTable').innerHTML = '<div class="text-xs text-red-400">Erreur de chargement</div>';
      return;
    }
    var data = await res.json();
    var g = document.getElementById('waGlobal');
    g.checked = !!data.global_api_key_unlimited;
    document.getElementById('waGlobalMsg').textContent = data.global_api_key_unlimited ? 'active' : 'desactive';
    var rows = (data.items || []).map(row).join('');
    document.getElementById('waTable').innerHTML = rows || '<div class="text-xs text-slate-500">Aucun compte</div>';
  };

  function row(u) {
    var q = u.override.web_daily_quota;
    var qv = (q === null || q === undefined) ? '' : q;
    return '<div class="border border-slate-800 rounded-lg p-3 flex flex-wrap items-center gap-3">' +
      '<div class="min-w-[180px]"><div class="text-xs text-white">' + esc(u.email) + '</div>' +
      '<div class="text-[10px] text-slate-500 font-mono">' + esc(u.user_id) + '</div></div>' +
      '<span class="text-[10px] px-2 py-0.5 rounded bg-slate-800 text-slate-300">' + esc(u.plan) + '</span>' +
      (u.has_api_key ? '<span class="text-[10px] px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-300 border border-emerald-500/30">cle API</span>' : '') +
      '<span class="text-[10px] ' + (u.unlimited ? 'text-emerald-300' : 'text-slate-400') + '">' +
        (u.unlimited ? 'illimite' : esc(u.used_today) + '/' + esc(u.effective_quota)) + '</span>' +
      '<label class="flex items-center gap-1 text-[11px] text-slate-300"><input type="checkbox" ' +
        (u.override.web_unlimited ? 'checked' : '') +
        ' onchange="waSet(\'' + u.user_id + '\',{web_unlimited:this.checked?1:0})"> illimite</label>' +
      '<input type="number" min="0" value="' + qv + '" placeholder="quota" class="w-20 bg-dark border border-slate-800 rounded px-2 py-1 text-[11px] text-slate-200"' +
        ' onchange="waSet(\'' + u.user_id + '\',{web_daily_quota:this.value===\'\'?-1:parseInt(this.value,10)})">' +
      '<button class="text-[11px] px-2 py-1 bg-slate-800 hover:bg-slate-700 rounded text-slate-300" onclick="waClear(\'' + u.user_id + '\')">defaut</button>' +
      '</div>';
  }

  window.waSet = async function (uid, obj) {
    await fetch('/admin/api/web-users/' + uid, {
      method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(obj)
    });
    window.waLoad();
  };
  window.waClear = async function (uid) {
    await fetch('/admin/api/web-users/' + uid + '/clear', { method: 'POST' });
    window.waLoad();
  };

  document.getElementById('waReload').onclick = function () { window.waLoad(); };
  document.getElementById('waSearch').addEventListener('keydown', function (e) { if (e.key === 'Enter') window.waLoad(); });
  document.getElementById('waGlobal').onchange = async function () {
    await fetch('/admin/api/web-access/global', {
      method: 'PATCH', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled: this.checked ? 1 : 0 })
    });
    window.waLoad();
  };
})();
