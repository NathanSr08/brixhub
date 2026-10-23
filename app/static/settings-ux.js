/* BrixHub - rend les reglages plus lisibles : booleens en liste, maintenance dedupliquee */
(function () {
  if (window.__bxSettingsUx) return;
  window.__bxSettingsUx = 1;
  var CACHER = ['maintenance_mode', 'maintenance_text'];

  function ameliorer() {
    document.querySelectorAll('[id^="st_"]').forEach(function (el) {
      var cle = el.id.slice(3);
      if (CACHER.indexOf(cle) !== -1) {
        var boite = el.parentElement;
        if (boite && boite.querySelectorAll('input,select,textarea').length > 1) boite = boite.parentElement;
        if (boite) boite.style.display = 'none';
        return;
      }
      if (el.tagName !== 'INPUT') return;
      var v = (el.value || '').trim();
      if (v !== '0' && v !== '1') return;
      var sel = document.createElement('select');
      sel.id = el.id;
      sel.className = el.className;
      sel.innerHTML = '<option value="0">Non</option><option value="1">Oui</option>';
      sel.value = v;
      el.replaceWith(sel);
    });
  }

  function brancher() {
    if (typeof window.loadSettings === 'function' && !window.__bxLsWrapped) {
      window.__bxLsWrapped = 1;
      var orig = window.loadSettings;
      window.loadSettings = function () {
        var r = orig.apply(this, arguments);
        setTimeout(ameliorer, 0);
        return r;
      };
    }
  }
  brancher();
  setInterval(function () { brancher(); ameliorer(); }, 1500);
})();
