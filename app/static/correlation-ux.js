/* BrixHub - pastilles de type de donnee + fenetres d'alerte stylisees */
(function () {
  if (window.__bxCorrUx) return;
  window.__bxCorrUx = 1;

  var COULEURS = {
    blue: 'bg-blue-500/10 text-blue-300 border-blue-500/30',
    emerald: 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30',
    purple: 'bg-purple-500/10 text-purple-300 border-purple-500/30',
    amber: 'bg-amber-500/10 text-amber-300 border-amber-500/30',
    cyan: 'bg-cyan-500/10 text-cyan-300 border-cyan-500/30',
    slate: 'bg-slate-500/10 text-slate-300 border-slate-500/30',
    red: 'bg-red-500/10 text-red-300 border-red-500/30'
  };
  var ICONES = {
    lock: 'fa-lock', info: 'fa-circle-info', clock: 'fa-clock', bolt: 'fa-bolt'
  };

  /* ======================= fenetre d'alerte ======================= */
  var dernier = { msg: '', ts: 0 };

  window.bxAlerte = function (a, b, c) {
    var titre, message, opts;
    if (b === undefined) { titre = 'Information'; message = String(a); opts = {}; }
    else { titre = String(a); message = String(b); opts = c || {}; }

    var now = Date.now();
    if (message === dernier.msg && (now - dernier.ts) < 1500) return;
    dernier = { msg: message, ts: now };

    var couleur = COULEURS[opts.couleur || 'amber'] || COULEURS.amber;
    var icone = ICONES[opts.icone || 'lock'] || ICONES.lock;

    var ov = document.createElement('div');
    ov.className = 'fixed inset-0 z-[999] flex items-center justify-center p-5 bg-black/70 backdrop-blur-sm';
    ov.innerHTML =
      '<div class="bg-surface border border-slate-800 rounded-2xl max-w-md w-full p-6 text-center shadow-2xl">' +
        '<div class="w-14 h-14 mx-auto rounded-2xl border flex items-center justify-center ' + couleur + '">' +
          '<i class="fa-solid ' + icone + ' text-xl"></i></div>' +
        '<h3 class="mt-4 text-lg font-bold text-white">' + titre + '</h3>' +
        '<p class="mt-2 text-xs text-slate-300 leading-relaxed">' + message + '</p>' +
        (opts.detail ? '<div class="mt-2 text-[10px] text-slate-500 font-mono">' + opts.detail + '</div>' : '') +
        (opts.telegram === false ? '' :
          '<a href="' + (opts.lien || 'https://t.me/leackfrench?text=' +
            encodeURIComponent('Bonjour, ' + message + (opts.detail ? ' (' + opts.detail + ')' : ''))) +
            '" target="_blank" rel="noopener" ' +
            'class="mt-5 block w-full py-3 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-sm font-semibold transition">' +
            '<i class="fa-brands fa-telegram mr-2"></i>Contacter @leackfrench</a>') +
        '<button class="mt-2 w-full py-2 text-xs text-slate-400 hover:text-white" ' +
          'onclick="this.closest(\'div.fixed\').remove()">Fermer</button>' +
      '</div>';
    document.body.appendChild(ov);
    ov.addEventListener('click', function (e) { if (e.target === ov) ov.remove(); });
  };

  /* ======================= pastilles de type ======================= */
  var ICONES_CHAMPS = [
    ['fa-phone', 'Telephone', 'blue'],
    ['fa-envelope', 'Email', 'emerald'],
    ['fa-at', 'Email', 'emerald'],
    ['fa-location-dot', 'Adresse', 'purple'],
    ['fa-house', 'Adresse', 'purple'],
    ['fa-map', 'Adresse', 'purple'],
    ['fa-user', 'Nom', 'amber'],
    ['fa-calendar', 'Naissance', 'cyan'],
    ['fa-city', 'Ville', 'slate'],
    ['fa-passport', 'Source', 'slate']
  ];
  var TEXTES = [
    [/^\+?\d[\d\s().-]{7,}$/, 'Telephone', 'blue'],
    [/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/, 'Email', 'emerald'],
    [/^\d{1,4}\s+[A-Z0-9À-Ü'’ -]{4,}$/, 'Adresse', 'purple']
  ];

  function pastille(txt, couleur) {
    var s = document.createElement('span');
    s.className = 'bx-tag inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-bold uppercase ' +
                  'tracking-wide border mr-1.5 align-middle ' + COULEURS[couleur];
    s.textContent = txt;
    return s;
  }
  function conteneur(el) {
    var cur = el.parentElement, i = 0;
    while (cur && i < 3) {
      var t = (cur.textContent || '').trim();
      if (t.length >= 3 && t.length <= 120) return cur;
      cur = cur.parentElement; i++;
    }
    return el.parentElement;
  }
  function modal() {
    var noeuds = document.querySelectorAll('div,section');
    for (var i = 0; i < noeuds.length; i++) {
      var t = noeuds[i].textContent || '';
      if (t.indexOf('M\u00eame Personne') !== -1 && t.indexOf('Foyer') !== -1) return noeuds[i];
    }
    return null;
  }
  function poser(boite, txt, couleur) {
    if (!boite || boite.getAttribute('data-bxtag')) return;
    boite.setAttribute('data-bxtag', '1');
    boite.insertBefore(pastille(txt, couleur), boite.firstChild);
  }
  function taguer() {
    var racine = modal();
    if (!racine) return;
    racine.querySelectorAll('i[class*="fa-"]').forEach(function (ic) {
      var cls = ic.className || '';
      for (var i = 0; i < ICONES_CHAMPS.length; i++) {
        if (cls.indexOf(ICONES_CHAMPS[i][0]) !== -1) {
          poser(conteneur(ic), ICONES_CHAMPS[i][1], ICONES_CHAMPS[i][2]); return;
        }
      }
    });
    racine.querySelectorAll('span,div,p,li').forEach(function (el) {
      if (el.children.length || el.getAttribute('data-bxtag')) return;
      var t = (el.textContent || '').trim();
      if (!t || t.length > 90) return;
      for (var i = 0; i < TEXTES.length; i++) {
        if (TEXTES[i][0].test(t)) { poser(el, TEXTES[i][1], TEXTES[i][2]); return; }
      }
    });
  }

  /* ======================= refus d'acces ======================= */
  var MESSAGES = {
    ACCOUNT_BANNED: ['Compte suspendu', 'Votre compte est suspendu ou l\u2019acces est refuse.'],
    ROUTE_DENIED: ['Acces restreint', 'Vous n\u2019avez pas les droits pour cette fonctionnalite.'],
    ROUTE_NOT_ALLOWED: ['Acces restreint', 'Votre profil n\u2019est pas autorise sur cette fonctionnalite.'],
    BLOCKED: ['Acces bloque', 'Votre acces a ete bloque par l\u2019administration.'],
    MAINTENANCE: ['Maintenance en cours', 'Le service est momentanement indisponible.']
  };

  function nomFonction(route) {
    if (/correlation/i.test(route)) return 'la correlation';
    if (/search|recherche/i.test(route)) return 'la recherche';
    if (/config/i.test(route)) return 'la configuration';
    return 'cette fonctionnalite';
  }

  function refus(route, motif) {
    var base = 'ROUTE_NOT_ALLOWED';
    var cles = Object.keys(MESSAGES);
    for (var i = 0; i < cles.length; i++) {
      if (String(motif || '').indexOf(cles[i]) !== -1) { base = cles[i]; break; }
    }
    var m = MESSAGES[base];
    var texte = m[1] +
      (base === 'MAINTENANCE' ? '' : ' Si vous pensez qu\u2019il s\u2019agit d\u2019une erreur, merci de contacter le support.');
    window.bxAlerte(m[0], texte, {
      detail: route + ' \u00b7 ' + motif,
      couleur: base === 'MAINTENANCE' ? 'blue' : (base === 'ACCOUNT_BANNED' ? 'red' : 'amber'),
      icone: base === 'MAINTENANCE' ? 'clock' : 'lock',
      lien: 'https://t.me/leackfrench?text=' + encodeURIComponent(
        'Bonjour, ' + nomFonction(route) + ' m\u2019est refusee (route ' + route + ', motif ' + motif + '). Merci de verifier mes droits.')
    });
  }


  /* ---- etat d'acces : bandeau dans la zone de resultats ---- */
  function zoneResultats() {
    return document.getElementById('results')
        || document.getElementById('resultsContainer')
        || document.getElementById('resultats')
        || document.getElementById('resultatsZone')
        || document.querySelector('[id*="result"]');
  }

  window.bxAvis = function (message, couleur) {
    var zone = zoneResultats();
    if (!zone) return;
    var d = document.getElementById('bxAvis');
    if (!d) {
      d = document.createElement('div');
      d.id = 'bxAvis';
      d.className = 'mb-4 px-4 py-3 rounded-xl border text-xs flex flex-wrap items-center gap-2';
      zone.insertBefore(d, zone.firstChild);
    }
    var tons = {
      amber: 'bg-amber-500/10 border-amber-500/30 text-amber-200',
      red: 'bg-red-500/10 border-red-500/30 text-red-200',
      slate: 'bg-slate-800/60 border-slate-700 text-slate-300'
    };
    d.className = 'mb-4 px-4 py-3 rounded-xl border text-xs flex flex-wrap items-center gap-2 ' + (tons[couleur] || tons.amber);
    d.innerHTML = '<i class="fa-solid fa-lock"></i><span>' + message + '</span>' +
      '<a class="ml-auto underline hover:no-underline" target="_blank" rel="noopener" ' +
      'href="https://t.me/leackfrench?text=' + encodeURIComponent('Bonjour, ' + message) + '">contacter le support</a>';
  };

  async function bxEtatAcces() {
    try {
      var r = await fetch('/api/access/me');
      if (!r.ok) return;
      var d = await r.json();
      window.__bxAcces = d;
      var f = d.fonctions || {};
      if (d.bloque) {
        window.bxAvis('Votre acces est bloque par l\u2019administration.', 'red');
        return;
      }
      if (f.recherche === false) {
        window.bxAvis('La recherche est desactivee pour votre compte.', 'amber');
        var b = document.querySelector('button[onclick*="search"], #searchBtn, button[type="submit"]');
        if (b) { b.classList.add('opacity-60'); b.title = 'Recherche desactivee pour votre compte'; }
      }
      if (f.correlation === false) {
        document.querySelectorAll('[onclick*="correlation"], [onclick*="Correlation"]').forEach(function (e) {
          e.title = 'Correlation desactivee pour votre compte';
          e.classList.add('opacity-70');
        });
      }
      if (f.sources === false || f.stats === false) {
        var z = document.querySelector('select[id*="source"], select[name="source"]');
        if (z && z.parentElement && !document.getElementById('bxAvisSources')) {
          z.disabled = true;
          z.classList.add('opacity-60', 'cursor-not-allowed');
          var note = document.createElement('div');
          note.id = 'bxAvisSources';
          note.className = 'mt-1 text-[10px] text-amber-300/80';
          note.textContent = 'indisponible : acces restreint';
          z.parentElement.appendChild(note);
        }
      }
    } catch (e) {}
  }

  /* sources / stats : avis discret, pas de fenetre */
  function avisDiscret(route) {
    if (/sources|stats/.test(route)) {
      window.bxAvis('Donnees d\u2019interface indisponibles (acces restreint).', 'slate');
      return true;
    }
    return false;
  }

  var vraiFetch = window.fetch;
  window.fetch = async function (entree, init) {
    var url = typeof entree === 'string' ? entree : (entree && entree.url) || '';
    var res = await vraiFetch.apply(this, arguments);
    if ((res.status === 403 || res.status === 503) && /\/api\/|\/v1\//.test(url)) {
      var motif = 'ACCES_REFUSE';
      try { var j = await res.clone().json(); motif = j.detail || motif; } catch (e) {}
      var route = url.split('?')[0].replace(location.origin, '');
      if (!avisDiscret(route)) refus(route, motif);
    }
    return res;
  };

  var tmr = null;
  new MutationObserver(function () {
    if (tmr) return;
    tmr = setTimeout(function () { tmr = null; taguer(); }, 150);
  }).observe(document.body, { childList: true, subtree: true });


  /* ---- tolerance : rien d'invente, on marque juste l'indisponible ---- */
  function bxTolerant() {
    try {
      var stats = document.querySelectorAll('[id*="stat"], [class*="stat"]');
      stats.forEach(function (e) {
        if ((e.textContent || '').trim() === '' || (e.textContent || '').trim() === '-') {
          e.setAttribute('title', 'indisponible : acces restreint');
        }
      });
    } catch (e) {}
  }
setInterval(bxTolerant, 2000);

  bxEtatAcces();
  taguer();
})();
