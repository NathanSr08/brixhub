/* =====================================================================
   BrixHub - Config dynamique des pages publiques (v3)

   1. Banniere + bandeau maintenance pilotables
   2. GRILLE TARIFAIRE de la doc API rendue depuis la base
      (uniquement les plans avec is_public = 1)
   3. Quotas reecrits automatiquement selon le contexte
   4. Regles manuelles optionnelles (ui_rules)
   ===================================================================== */
(function () {
    'use strict';

    var CFG = null;
    var QRE = /(\d+(?:[ \u202f]\d{3})*)(\s*(?:requ[eê]tes?|req|recherches?))/gi;
    var PRICE_RE = /(\d+(?:[.,]\d{1,2})?)\s*(?:€|EUR|\$|USD)/i;
    var SKIP = { SCRIPT: 1, STYLE: 1, TEXTAREA: 1, NOSCRIPT: 1, INPUT: 1, SELECT: 1 };

    /* --------------------------- outils --------------------------- */
    function esc(v) {
        return String(v === null || v === undefined ? '' : v)
            .replace(/[&<>"']/g, function (c) {
                return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
            });
    }
    function nf(n) { return String(Math.round(Number(n) || 0)).replace(/\B(?=(\d{3})+(?!\d))/g, ' '); }

    function fmt(v, cur) {
        var n = Number(v || 0);
        var s = n.toFixed(2).replace('.', ',');
        if (s.slice(-3) === ',00') s = s.slice(0, -3);
        var tpl = cur === 'usd' ? (CFG.price_format_usd || '${value}')
                                : (CFG.price_format_eur || '{value} EUR');
        return tpl.replace('{value}', s);
    }

    function subst(tpl, cfg) {
        if (cfg) {
            if (cfg.plan != null) tpl = String(tpl).split('{plan}').join(cfg.plan);
            if (cfg.price != null) tpl = String(tpl).split('{price}').join(cfg.price);
        }
        cfg = cfg || CFG || {};
        return String(tpl || '').replace(/\{([^}]+)\}/g, function (m, key) {
            if (key === 'guest_daily_quota') return cfg.guest_daily_quota;
            if (key === 'user_daily_quota') return cfg.user_daily_quota;
            if (key === 'guest_rps') return cfg.global_rps_guest;
            if (key === 'user_rps') return cfg.global_rps_user;
            var p = key.split(':');
            if (p.length === 3 && (p[0] === 'plan' || p[0] === 'del')) {
                var src = p[0] === 'plan' ? cfg.plans : cfg.deletion_plans;
                var pl = (src || []).find(function (x) { return x.plan_id === p[1]; });
                if (!pl) return m;
                if (p[2] === 'price_eur') return fmt(pl.price_eur, 'eur');
                if (p[2] === 'price_usd') return fmt(pl.price_usd, 'usd');
                return pl[p[2]];
            }
            return m;
        });
    }

    function textNodes(root) {
        var out = [], w = document.createTreeWalker(root || document.body, NodeFilter.SHOW_TEXT, {
            acceptNode: function (n) {
                var p = n.parentNode;
                if (!p || SKIP[p.nodeName]) return NodeFilter.FILTER_REJECT;
                return NodeFilter.FILTER_ACCEPT;
            }
        });
        var n; while ((n = w.nextNode())) out.push(n);
        return out;
    }

    function byText(re, tag) {
        var els = document.querySelectorAll(tag || 'h1,h2,h3,div,span,p');
        for (var i = 0; i < els.length; i++) {
            if (re.test((els[i].textContent || '').trim()) && els[i].children.length < 3) return els[i];
        }
        return null;
    }

    /* =================== 1. GRILLE TARIFAIRE =================== */
    function findPricingGrid() {
        var btns = [];
        document.querySelectorAll('button, a').forEach(function (b) {
            var t = (b.textContent || '').trim();
            if (/^(Prendre|Choisir|Souscrire|Contacter|Commander)/i.test(t)) btns.push(b);
        });
        if (btns.length < 2) return null;

        function climb(el) {
            var e = el;
            for (var i = 0; i < 5 && e; i++) {
                var t = e.textContent || '';
                if (/requ[êe]tes?\s*\/\s*jour|Sans engagement|Sur mesure|req\/sec|Acc[eè]s /i.test(t)
                    && e.children.length <= 6) return e;
                e = e.parentElement;
            }
            return el.parentElement;
        }

        var cards = btns.map(climb).filter(Boolean);
        if (cards.length < 2) return null;
        var parent = cards[0].parentElement;
        if (!parent) return null;
        var same = cards.every(function (c) { return c.parentElement === parent; });
        return same ? parent : (parent.parentElement || null);
    }

    function featuresOf(p) {
        try {
            var f = JSON.parse(p.features || '[]');
            if (Array.isArray(f) && f.length) return f;
        } catch (e) { }
        var out = [];
        out.push(Number(p.daily_quota) >= 999999 ? 'Requêtes illimitées' : nf(p.daily_quota) + ' requêtes / jour');
        out.push('Accès /v1/search');
        if (Number(p.rate_limit_rps) >= 20 || p.web_unlimited) out.push('Accès complet /v1/search + /v1/correlations');
        if (Number(p.rate_limit_rps) > 0) out.push('Débit ' + p.rate_limit_rps + ' req/sec');
        if (p.web_unlimited) out.push('Accès web illimité');
        return out;
    }

    function isContact(p) { return Number(p.price_eur) <= 0; }

    function ctaUrl(p) {
        return isContact(p) ? (CFG.contact_url || 'mailto:contact@brixhub.uned.live')
                            : ('https://t.me/'+(CFG.telegram_handle||'leackfrench')+'?text='+encodeURIComponent('Bonjour, je souhaite le plan '+((typeof p!=='undefined'&&p)?(p.label||p.plan_id):'')+' ('+((CFG.price_format_eur||'{value} EUR').replace('{value}',(typeof p!=='undefined'&&p)?p.price_eur:''))+')'));
    }
    function ctaLabel(p) {
        if (isContact(p)) return CFG.contact_label || "Contacter l'équipe";
        return subst(CFG.cta_label || 'Prendre {plan} ({price})', Object.assign({}, CFG, {plan:(typeof p!=='undefined'&&p)?(p.label||p.plan_id):'',price:(typeof p!=='undefined'&&p)?((CFG.price_format_eur||'{value} EUR').replace('{value}',p.price_eur)):''}),
                     Object.assign({}, CFG, { plan: p.label || p.plan_id, price: fmt(p.price_eur, 'eur') }));
    }

    function cardHtml(p, recommended) {
        var contact = isContact(p);
        var price = contact ? 'Sur mesure' : fmt(p.price_eur, 'eur');
        var feats = featuresOf(p);
        return '<div style="position:relative;display:flex;flex-direction:column;gap:16px;background:#0f1420;' +
            'border:1px solid ' + (recommended ? '#6366f1' : '#1f2937') + ';border-radius:16px;padding:24px;' +
            (recommended ? 'box-shadow:0 0 0 1px rgba(99,102,241,.5),0 12px 40px rgba(99,102,241,.15);' : '') + '">' +
            (recommended ? '<span style="position:absolute;top:-11px;left:50%;transform:translateX(-50%);background:#6366f1;' +
                'color:#fff;font-size:10px;font-weight:700;letter-spacing:.08em;padding:4px 12px;border-radius:999px;">RECOMMANDÉ</span>' : '') +
            '<span style="align-self:flex-start;font-size:10px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;' +
            'color:' + (recommended ? '#a5b4fc' : '#94a3b8') + ';background:rgba(148,163,184,.1);border:1px solid rgba(148,163,184,.2);' +
            'padding:3px 8px;border-radius:6px;">' + esc(p.label || p.plan_id) + '</span>' +
            '<div><span style="font-size:34px;font-weight:800;color:#fff;letter-spacing:-.02em;">' + esc(price) + '</span>' +
            (contact ? '' : '<span style="color:#64748b;font-size:13px;"> / mois</span>') +
            '<div style="color:#34d399;font-size:12px;margin-top:2px;">Sans engagement</div></div>' +
            '<ul style="list-style:none;padding:0;margin:0;display:flex;flex-direction:column;gap:8px;font-size:13px;color:#cbd5e1;">' +
            feats.map(function (f) {
                return '<li style="display:flex;gap:8px;align-items:flex-start;"><span style="color:#34d399;">&#10003;</span><span>' + esc(f) + '</span></li>';
            }).join('') + '</ul>' +
            '<a href="' + esc(ctaUrl(p)) + '" style="margin-top:auto;display:block;text-align:center;padding:10px;border-radius:10px;' +
            'font-size:13px;font-weight:600;text-decoration:none;' +
            (recommended ? 'background:#4f46e5;color:#fff;' : 'background:#1e293b;color:#e2e8f0;border:1px solid #334155;') + '">' +
            esc(ctaLabel(p)) + '</a></div>';
    }

    function renderPricing() {
        var plans = (CFG.plans || []).slice()
            .sort(function (a, b) { return (a.sort_order || 0) - (b.sort_order || 0); });
        if (!plans.length) return;

        // titres
        if (CFG.pricing_title) {
            var h = byText(/plans?\s*&?\s*licences?/i, 'h1,h2,h3');
            if (h) h.textContent = CFG.pricing_title;
        }
        if (CFG.pricing_subtitle) {
            var p = byText(/quotas? journaliers?|sans engagement/i, 'p,div,span');
            if (p && p.children.length === 0) p.textContent = CFG.pricing_subtitle;
        }

        var grid = findPricingGrid();
        if (!grid) return;
        grid.setAttribute('data-bx-pricing', '1');
        var html = plans.map(function (pl) {
            return cardHtml(pl, pl.plan_id === CFG.recommended_plan);
        }).join('');
        if (grid.__bxLast === html) return;
        grid.__bxLast = html;
        grid.innerHTML = html;
    }

    /* ==================== 2. QUOTAS AUTOMATIQUES ==================== */
    var GUEST_RE = /(invit\w*|guest|anonym\w*|visiteur\w*)/gi;
    var USER_RE = /(compte|connect\w*|membre|utilisateur\w*|inscri\w*)/gi;

    function nearestQuota(block, pos) {
        function dist(re) {
            var m, best = Infinity; re.lastIndex = 0;
            while ((m = re.exec(block))) {
                var d = Math.abs(m.index + m[0].length / 2 - pos);
                if (d < best) best = d;
            }
            return best;
        }
        var dg = dist(GUEST_RE), du = dist(USER_RE);
        if (dg === Infinity && du === Infinity) return null;
        return dg <= du ? CFG.guest_daily_quota : CFG.user_daily_quota;
    }

    function rewriteQuotas(node) {
        var t = node.nodeValue;
        if (!t || !/\d/.test(t)) return;
        var p = node.parentNode;
        if (p && p.closest && p.closest('[data-bx-pricing]')) return;

        QRE.lastIndex = 0;
        if (!QRE.test(t)) return;

        var block = (p && p.textContent) || t;
        var base = block.indexOf(t);
        if (base < 0) base = 0;

        QRE.lastIndex = 0;
        var out = t.replace(QRE, function (m, num, rest, offset) {
            var q = nearestQuota(block, base + offset);
            return (q === null ? num : q) + rest;
        });
        if (out !== t) node.nodeValue = out;
    }

    /* ====================== 3. PRIX (hors grille) ====================== */
    function replaceFirstPrice(host, newPrice) {
        var nodes = textNodes(host);
        for (var i = 0; i < nodes.length; i++) {
            if (PRICE_RE.test(nodes[i].nodeValue)) {
                nodes[i].nodeValue = nodes[i].nodeValue.replace(PRICE_RE, newPrice);
                return true;
            }
        }
        return false;
    }

    function autoPrices() {
        (CFG.plans || []).concat(CFG.deletion_plans || []).forEach(function (pl) {
            if (!pl || !pl.label) return;
            var node = textNodes(document.body).find(function (n) {
                return n.nodeValue.toLowerCase().indexOf(pl.label.toLowerCase()) !== -1;
            });
            if (!node) return;
            var host = node.parentNode;
            for (var k = 0; k < 6 && host; k++) {
                if (host.getAttribute && host.getAttribute('data-bx-pricing')) return;
                if (replaceFirstPrice(host, fmt(pl.price_eur, 'eur'))) return;
                host = host.parentNode;
            }
        });
    }

    /* ========================= 4. BANNIERE ========================= */
    var COLORS = {
        info: 'background:rgba(37,99,235,.15);border-color:rgba(29,78,216,.5);color:#dbeafe;',
        warning: 'background:rgba(217,119,6,.15);border-color:rgba(180,83,9,.5);color:#fef3c7;',
        danger: 'background:rgba(220,38,38,.15);border-color:rgba(185,28,28,.5);color:#fee2e2;',
        success: 'background:rgba(5,150,105,.15);border-color:rgba(4,120,87,.5);color:#d1fae5;'
    };

    function banner(cfg) {
        var b = cfg.banner || {};
        var old = document.getElementById('bxBanner');
        if (!b.enabled) { if (old) old.remove(); return; }
        var el = old || document.createElement('div');
        el.id = 'bxBanner';
        el.setAttribute('style', 'position:relative;width:100%;border-bottom:1px solid;padding:10px 40px;' +
            'text-align:center;font-size:13px;font-weight:500;z-index:60;' + (COLORS[b.type] || COLORS.info));
        el.innerHTML = '<i class="fa-solid fa-bullhorn" style="margin-right:8px;"></i>' +
            esc(subst(b.text || 'Annonce BrixHub', cfg)) +
            '<span onclick="this.parentNode.remove()" style="position:absolute;right:12px;top:50%;transform:translateY(-50%);cursor:pointer;opacity:.7;">&#10005;</span>';
        if (!old) document.body.insertBefore(el, document.body.firstChild);
    }

    function maintenance(cfg) {
        var el = document.getElementById('bxMaintenance');
        if (!cfg.maintenance_mode) { if (el) el.remove(); return; }
        if (!el) {
            el = document.createElement('div');
            el.id = 'bxMaintenance';
            el.setAttribute('style', 'position:fixed;bottom:16px;right:16px;z-index:60;max-width:280px;' +
                'background:#d97706;color:#fff;border-radius:12px;padding:12px 16px;font-size:12px;box-shadow:0 12px 30px rgba(0,0,0,.4);');
            document.body.appendChild(el);
        }
        el.innerHTML = '<b>Maintenance</b><br>' + esc(subst(cfg.maintenance_text || '', cfg));
    }

    /* ======================== application ======================== */
    function rulesApply(node) {
        if (!(CFG.ui_rules || []).length) return;
        var t = node.nodeValue, out = t;
        CFG.ui_rules.forEach(function (r) {
            if (!r || !r.find) return;
            out = out.split(r.find).join(subst(r.replace || '', CFG));
        });
        if (out !== t) node.nodeValue = out;
    }

    function applyAll() {
        if (!CFG) return;
        banner(CFG);
        maintenance(CFG);
        var nodes = textNodes(document.body);
        for (var i = 0; i < nodes.length; i++) {
            rulesApply(nodes[i]);
            rewriteQuotas(nodes[i]);
        }
        autoPrices();
        renderPricing(); try{window.__bxFixPlans&&window.__bxFixPlans();}catch(e){}
    }

    function refresh() {
        fetch('/api/config', { cache: 'no-store' })
            .then(function (r) { return r.ok ? r.json() : null; })
            .then(function (cfg) {
                if (!cfg) { console.warn('[BrixHub] /api/config indisponible'); return; }
                CFG = cfg;
                window.BX_CONFIG = cfg;
                applyAll();
            })
            .catch(function (e) { console.warn('[BrixHub] config KO', e); });
    }

    window.bxApplyConfig = refresh;
    window.bxSubst = function (t) { return CFG ? subst(t, CFG) : t; };
    window.bxPrice = function (v, c) { return CFG ? fmt(v, c || 'eur') : v; };
    window.bxDebug = function () {
        console.log('config :', CFG ? 'chargee' : 'absente');
        console.log('plans publics :', CFG ? (CFG.plans || []).length : 0);
        console.log('grille trouvee :', !!findPricingGrid());
        console.log('banniere :', CFG && CFG.banner);
    };

    var pending = null;
    var obs = new MutationObserver(function () {
        clearTimeout(pending);
        pending = setTimeout(applyAll, 120);
    });

    function start() {
        refresh();
        obs.observe(document.body, { childList: true, subtree: true });
        setInterval(refresh, 60000);
    }

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
    else start();
})();
/* ---- plan-cta inlined ---- */
/* BrixHub - CTA des plans : libelle/prix depuis la base + Telegram */
(function () {
  if (window.__bxPlanCta) return;
  window.__bxPlanCta = 1;
  var cfg = null, catalog = [];
  var CTA_RE = /prendre|supprimer|nettoyer|wipeout|contacter|choisir|commander|souscrire/i;

  function esc(s) { return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }
  function norm(s) {
    return String(s == null ? '' : s).toLowerCase()
      .replace(/[&•·_\-.\/]+/g, ' ').replace(/\s+/g, ' ').trim();
  }
  function fmtPrice(v) { return ((cfg && cfg.price_format_eur) || '{value} EUR').replace('{value}', String(v)); }
  function handle() { return (cfg && cfg.telegram_handle) || 'leackfrench'; }
  function tgUrl(m) { return 'https://t.me/' + handle() + '?text=' + encodeURIComponent(m); }

  function matchesIn(el) {
    var txt = ' ' + norm(el.textContent) + ' ', out = [];
    for (var j = 0; j < catalog.length; j++) {
      var names = [catalog[j].label, catalog[j].plan_id];
      for (var k = 0; k < names.length; k++) {
        var lab = norm(names[k]);
        if (lab.length < 2) continue;
        if (new RegExp('(^| )' + esc(lab) + '( |$)').test(txt)) { out.push(catalog[j]); break; }
      }
    }
    return out;
  }
  function planFromCatalog(el) {
    var cur = el;
    for (var i = 0; i < 7 && cur; i++, cur = cur.parentElement) {
      var m = matchesIn(cur);
      if (m.length === 1) return m[0];
      if (m.length > 1) return null;
    }
    return null;
  }
  function cardOf(el) {
    var cur = el;
    for (var i = 0; i < 7 && cur; i++, cur = cur.parentElement) {
      if (/(\d[\d\s.,]*)\s*(EUR|€|\$)/i.test(cur.textContent || '')) return cur;
    }
    return null;
  }
  function domLabel(card) {
    var els = card.querySelectorAll('*');
    for (var i = 0; i < els.length; i++) {
      var e = els[i];
      if (e.children.length) continue;
      var t = (e.textContent || '').trim();
      if (!t || t.length > 30 || /eur|€|\$/i.test(t)) continue;
      if (t !== t.toUpperCase() || !/[A-Z]/.test(t)) continue;
      if (CTA_RE.test(t)) continue;
      return t;
    }
    return null;
  }
  function domPrice(card) {
    var m = (card.textContent || '').match(/(\d[\d\s.,]*)\s*(EUR|€|\$)/i);
    return m ? m[1].replace(/\s+/g, '') : null;
  }

  function asLink(el, url) {
    if (el.tagName === 'A') { el.href = url; el.target = '_blank'; el.rel = 'noopener noreferrer'; return; }
    var a = document.createElement('a');
    a.className = el.className;
    a.innerHTML = el.innerHTML;
    a.href = url; a.target = '_blank'; a.rel = 'noopener noreferrer';
    a.style.display = 'inline-flex'; a.style.alignItems = 'center';
    a.style.justifyContent = 'center'; a.style.textDecoration = 'none';
    a.removeAttribute('onclick');
    el.replaceWith(a);
  }

  function fix() {
    var els = document.querySelectorAll('a,button,[role="button"]');
    for (var i = 0; i < els.length; i++) {
      var el = els[i], t = (el.textContent || '').trim();
      if (!CTA_RE.test(t)) continue;
      var p = planFromCatalog(el), label = null, price = null, api = true;
      if (p) { label = p.label || p.plan_id; price = fmtPrice(p.price_eur); api = !!p._api; }
      else {
        var card = cardOf(el);
        if (card) { label = domLabel(card); var raw = domPrice(card); if (label && raw) price = fmtPrice(raw); }
      }
      var msg;
      if (label && price) {
        if (t.indexOf('{plan}') !== -1 || t.indexOf('{price}') !== -1) {
          el.textContent = t.replace(/\{plan\}/g, label).replace(/\{price\}/g, price);
        } else if (/^prendre/i.test(t)) {
          var want = 'Prendre ' + label + ' (' + price + ')';
          if (t !== want) el.textContent = want;
        }
        msg = (api ? 'Bonjour, je souhaite le plan ' : 'Bonjour, je souhaite ') + label + ' (' + price + ')';
      } else if (/contact/i.test(t)) { msg = 'Bonjour, je souhaite un plan sur mesure'; }
      else continue;
      asLink(el, tgUrl(msg));
    }
  }
  window.__bxFixPlans = fix;

  async function run() {
    var c = window.__bxConfig ? await window.__bxConfig() : null;
    if (!c) {
      try { var r = await fetch('/api/config', { cache: 'no-store' }); if (r.ok) c = await r.json(); } catch (e) {}
    }
    if (!c) return;
    cfg = c; catalog = [];
    (cfg.plans || []).forEach(function (x) { x._api = true; catalog.push(x); });
    (cfg.deletion_plans || []).forEach(function (x) { x._api = false; catalog.push(x); });
    fix();
  }

  var tmr = null;
  function schedule() { if (tmr) return; tmr = setTimeout(function () { tmr = null; fix(); }, 150); }

  run();
  setInterval(fix, 400);
  setInterval(run, 15000);
  new MutationObserver(schedule).observe(document.body, { childList: true, subtree: true });
})();

