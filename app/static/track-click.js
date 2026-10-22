/* =====================================================================
   BrixHub - Tracking des clics sur les fiches resultats
   Detecte les cartes rendues, les marque, et poste le clic sur
   /api/track/click (acteur + fiche + criteres de recherche).
   ===================================================================== */
(function () {
    'use strict';

    var LAST_RESULTS = [], LAST_CRITERIA = '', tagTimer = null;

    function norm(s) {
        return String(s === null || s === undefined ? '' : s)
            .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
            .toUpperCase().replace(/\s+/g, ' ').trim();
    }

    /* --------- interception des recherches --------- */
    var origFetch = window.fetch;
    window.fetch = function (input, init) {
        var url = typeof input === 'string' ? input : (input && input.url) || '';
        var p = origFetch.apply(this, arguments);
        if (/\/(api|v1)\/search\b/.test(url)) {
            try { LAST_CRITERIA = decodeURIComponent((url.split('?')[1] || '')); } catch (e) { }
            p.then(function (res) {
                res.clone().json().then(function (list) {
                    if (Array.isArray(list)) {
                        LAST_RESULTS = list;
                        scheduleTag();
                    }
                }).catch(function () { });
            }).catch(function () { });
        }
        return p;
    };

    function scheduleTag() { clearTimeout(tagTimer); tagTimer = setTimeout(tagResults, 80); }

    /* --------- detection des cartes --------- */
    function sig(r) { return norm((r.Nom || r.nom || '') + ' ' + (r.Prenom || r.prenom || '')); }

    function pickCard(r) {
        var s = sig(r);
        if (!s) return null;
        var ville = norm(r.ville || r.Ville || '');
        var cp = norm(r['code postal'] || r.code_postal || '');
        var tel = norm(r['numero de tel'] || r.numero_tel || '');
        var all = document.querySelectorAll('div,li,tr,article,section,td,a,button,span');
        var cands = [];
        for (var i = 0; i < all.length; i++) {
            var el = all[i];
            if (el.offsetParent === null) continue;
            var t = norm(el.textContent);
            if (t.indexOf(s) === -1) continue;
            if (t.length > 700) continue;
            var extra = 0;
            if (ville && t.indexOf(ville) !== -1) extra++;
            if (cp && t.indexOf(cp) !== -1) extra++;
            if (tel && t.indexOf(tel) !== -1) extra++;
            cands.push({ el: el, extra: extra, len: t.length });
        }
        if (!cands.length) return null;
        cands.sort(function (a, b) { return (b.extra - a.extra) || (b.len - a.len); });
        return cands[0].el;
    }

    function tagResults() {
        if (!LAST_RESULTS.length) return;
        var n = 0;
        for (var i = 0; i < LAST_RESULTS.length; i++) {
            var r = LAST_RESULTS[i];
            if (!r || !r.profile_ref) continue;
            var el = pickCard(r);
            if (!el) continue;
            if (!el.dataset.profileRef) {
                el.dataset.profileRef = r.profile_ref;
                el.__bxResult = r;
                el.style.cursor = 'pointer';
                n++;
            }
        }
        if (n) console.log('[BrixHub] ' + n + ' fiche(s) marquee(s) pour le tracking');
    }

    /* --------- envoi du clic --------- */
    function send(r, ref) {
        var body = {
            profile_ref: ref,
            nom: r.Nom || r.nom || '',
            prenom: r.Prenom || r.prenom || '',
            date_naissance: r['Date de naissance'] || r.date_naissance || '',
            ville: r.ville || r.Ville || '',
            code_postal: r['code postal'] || r.code_postal || '',
            mail: r.mail || '',
            tel: r['numero de tel'] || r.numero_tel || '',
            source: r.source || '',
            criteria: LAST_CRITERIA,
            rank: LAST_RESULTS.indexOf(r) + 1,
            result_count: LAST_RESULTS.length
        };
        fetch('/api/track/click', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
            keepalive: true
        }).catch(function () { });
    }

    document.addEventListener('click', function (ev) {
        var el = ev.target && ev.target.closest ? ev.target.closest('[data-profile-ref]') : null;
        if (!el || !el.__bxResult) return;
        var now = Date.now();
        if (el.__bxLastClick && now - el.__bxLastClick < 800) return;
        el.__bxLastClick = now;
        send(el.__bxResult, el.dataset.profileRef);
    }, true);

    /* --------- re-scan continu --------- */
    new MutationObserver(function () { scheduleTag(); })
        .observe(document.body, { childList: true, subtree: true });

    window.bxTagResults = tagResults;
    window.bxDebugClicks = function () {
        console.log('resultats en memoire : ' + LAST_RESULTS.length +
            ' | cartes marquees : ' + document.querySelectorAll('[data-profile-ref]').length);
        console.log('criteres : ' + (LAST_CRITERIA || '(aucun)'));
    };
})();
