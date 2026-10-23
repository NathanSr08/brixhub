/* BrixHub - admin adaptatif : telephone, tablette, ordinateur */
(function () {
  if (window.__bxAdminResp) return;
  window.__bxAdminResp = 1;

  // 1. viewport si absent
  if (!document.querySelector('meta[name="viewport"]')) {
    var m = document.createElement('meta');
    m.name = 'viewport';
    m.content = 'width=device-width, initial-scale=1';
    document.head.appendChild(m);
  }

  // 2. feuille de style adaptative
  var css = document.createElement('style');
  css.id = 'bx-admin-responsive';
  css.textContent = [
    'body{overflow-x:hidden}',
    '.bx-tabs{overflow-x:auto;overflow-y:hidden;flex-wrap:nowrap;scrollbar-width:thin}',
    '.bx-tabs::-webkit-scrollbar{height:4px}',
    '.bx-tabs::-webkit-scrollbar-thumb{background:#1f293d;border-radius:3px}',
    '.bx-tabs>button{flex:0 0 auto;white-space:nowrap}',
    '.bx-scroll-x{overflow-x:auto;-webkit-overflow-scrolling:touch}',
    '.bx-scroll-x::-webkit-scrollbar{height:5px}',
    '.bx-scroll-x::-webkit-scrollbar-thumb{background:#1f293d;border-radius:3px}',

    '@media (max-width:767px){',
    '  main{padding-left:.6rem !important;padding-right:.6rem !important;padding-top:.9rem !important}',
    '  header .max-w-7xl{height:3rem !important}',
    '  .bx-stack{grid-template-columns:1fr !important}',
    '  .bx-scroll-x table{min-width:540px}',
    '  table{font-size:11px !important}',
    '  th,td{padding-left:.45rem !important;padding-right:.45rem !important}',
    '  input,select,textarea{font-size:12px !important;min-height:2.4rem}',
    '  button{min-height:2.2rem}',
    '  .bx-kpi{padding:.7rem !important}',
    '  .bx-kpi .text-xl,.bx-kpi .sm\\:text-2xl{font-size:1.15rem !important}',
    '  [class*="max-w-md"],[class*="max-w-lg"],[class*="max-w-xl"]{max-width:100% !important}',
    '}',

    '@media (min-width:768px) and (max-width:1023px){',
    '  main{padding-left:1rem !important;padding-right:1rem !important}',
    '  .bx-scroll-x table{min-width:680px}',
    '  .bx-stack{grid-template-columns:repeat(2,minmax(0,1fr)) !important}',
    '}',

    '@media (min-width:1536px){',
    '  main{max-width:1500px}',
    '}'
  ].join('\n');
  document.head.appendChild(css);

  function barreOnglets() {
    var btns = document.querySelectorAll('[id^="tabBtn"]');
    if (!btns.length) return;
    var barre = btns[0].parentElement;
    if (barre && !barre.classList.contains('bx-tabs')) {
      barre.classList.add('bx-tabs');
      var conteneur = barre.parentElement;
      if (conteneur) {
        conteneur.classList.add('sticky', 'top-12', 'sm:top-14', 'z-30',
                               'bg-dark/95', 'backdrop-blur', 'py-2', '-mb-1');
      }
      btns.forEach(function (b) {
        b.addEventListener('click', function () {
          try { b.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' }); } catch (e) {}
        });
      });
    }
  }

  function tableaux() {
    document.querySelectorAll('table').forEach(function (t) {
      var p = t.parentElement;
      if (!p) return;
      if (p.classList.contains('overflow-x-auto') || p.classList.contains('bx-scroll-x')) return;
      p.classList.add('bx-scroll-x');
    });
  }

  function grilles() {
    document.querySelectorAll('[class*="grid-cols-"]').forEach(function (g) {
      var cls = g.className || '';
      if (/grid-cols-[2-9]/.test(cls) && !/grid-cols-1\b/.test(cls)) g.classList.add('bx-stack');
    });
  }

  function kpis() {
    document.querySelectorAll('div').forEach(function (d) {
      var cls = d.className || '';
      if (cls.indexOf('rounded-xl') !== -1 && cls.indexOf('border') !== -1 &&
          d.querySelector('.text-xl, .sm\\:text-2xl')) d.classList.add('bx-kpi');
    });
  }

  function appliquer() { barreOnglets(); tableaux(); grilles(); kpis(); }

  appliquer();
  new MutationObserver(function () { setTimeout(appliquer, 80); })
    .observe(document.body, { childList: true, subtree: true });
})();
