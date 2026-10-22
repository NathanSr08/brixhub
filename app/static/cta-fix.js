/* BrixHub - remplace les placeholders {plan}/{price} par les valeurs reelles de la base */
(function () {
  var cfg = null, plans = [];

  function fmtPrice(p) {
    var f = (cfg && cfg.price_format_eur) || '{value} EUR';
    return f.replace('{value}', String(p.price_eur));
  }
  function esc(s) { return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }

  function innermost(el) {
    var k = el.children;
    for (var i = 0; i < k.length; i++) {
      var t = k[i].textContent || '';
      if (t.indexOf('{plan}') !== -1 || t.indexOf('{price}') !== -1) return false;
    }
    return true;
  }

  function findPlan(el) {
    var cur = el;
    for (var i = 0; i < 6 && cur; i++, cur = cur.parentElement) {
      var txt = cur.textContent || '';
      for (var j = 0; j < plans.length; j++) {
        var lab = (plans[j].label || plans[j].plan_id || '').trim();
        if (lab.length < 2) continue;
        if (new RegExp('(^|[^A-Za-z0-9])' + esc(lab) + '([^A-Za-z0-9]|$)', 'i').test(txt)) return plans[j];
      }
    }
    return null;
  }

  function fix() {
    var all = document.querySelectorAll('button, a, span, div, p');
    for (var i = 0; i < all.length; i++) {
      var el = all[i], t = el.textContent || '';
      if (t.indexOf('{plan}') === -1 && t.indexOf('{price}') === -1) continue;
      if (!innermost(el)) continue;
      var p = findPlan(el);
      if (!p) continue;
      var nt = t.replace(/\{plan\}/g, p.label || p.plan_id).replace(/\{price\}/g, fmtPrice(p));
      if (nt !== t) el.textContent = nt;
    }
  }

  async function run() {
    try {
      var r = await fetch('/api/config', { cache: 'no-store' });
      if (!r.ok) return;
      cfg = await r.json();
      plans = cfg.plans || [];
      fix();
    } catch (e) {}
  }

  run();
  setInterval(run, 5000);
})();
