/* BrixHub - badge quota + cache de config partage (1 seul appel /api/config) */
(function () {
  var lastCfg = null, timer = null;

  window.__bxConfig = window.__bxConfig || (function () {
    var cache = null, ts = 0, inflight = null;
    return function () {
      if (cache && Date.now() - ts < 15000) return Promise.resolve(cache);
      if (inflight) return inflight;
      inflight = fetch('/api/config', { cache: 'no-store' })
        .then(function (r) { return r.ok ? r.json() : cache; })
        .then(function (j) { if (j) { cache = j; ts = Date.now(); } return cache; })
        .catch(function () { return cache; })
        .then(function (v) { inflight = null; return v; });
      return inflight;
    };
  })();

  function kindOf(el) {
    var cur = el;
    for (var i = 0; i < 4 && cur; i++, cur = cur.parentElement) {
      var t = (cur.textContent || '').slice(0, 160);
      if (/visit|invit|guest/i.test(t)) return 'guest';
      if (/connect|compte|utilisateur|user|membre/i.test(t)) return 'user';
    }
    return null;
  }

  function apply(cfg) {
    if (!cfg) return;
    var w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null), n, nodes = [];
    while ((n = w.nextNode())) if (/req\s*\/\s*jour/i.test(n.nodeValue || '')) nodes.push(n);
    nodes.forEach(function (node) {
      var k = kindOf(node.parentElement);
      var v = k === 'guest' ? cfg.guest_daily_quota : k === 'user' ? cfg.user_daily_quota : null;
      if (v == null) return;
      var nv = node.nodeValue.replace(/\d+/, String(v));
      if (nv !== node.nodeValue) node.nodeValue = nv;
    });
  }

  async function run() {
    var cfg = await window.__bxConfig();
    if (!cfg) return;
    lastCfg = cfg; apply(cfg);
  }
  function schedule() { if (timer) return; timer = setTimeout(function () { timer = null; apply(lastCfg); }, 120); }

  run();
  setInterval(run, 15000);
  new MutationObserver(schedule).observe(document.body, { childList: true, subtree: true });
})();
