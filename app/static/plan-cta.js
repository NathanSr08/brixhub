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
