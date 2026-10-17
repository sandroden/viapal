// Preparazione della pagina per le riprese: si inietta con `agent-browser eval`
// dopo ogni caricamento completo (la navigazione interna della SPA lo conserva).
// - cursore finto: Chrome headless non disegna il puntatore, senza un segno
//   visibile sembra che l'interfaccia si muova da sola;
// - un'onda a ogni clic, per far leggere il gesto;
// - via gli elementi da sviluppo e i banner che distraggono.
(() => {
  if (window.__scena) return;
  window.__scena = true;

  const css = document.createElement('style');
  css.textContent = `
    .env-ribbon, .vp-inst-banner, [data-testid="installa-banner"] { display: none !important; }
    ::-webkit-scrollbar { width: 0 !important; height: 0 !important; }
    #__cursore {
      position: fixed; left: 0; top: 0; width: 26px; height: 26px; z-index: 2147483647;
      pointer-events: none; transform: translate(960px, 1200px);
      transition: transform 0.75s cubic-bezier(.45,.05,.25,1);
    }
    #__cursore svg { filter: drop-shadow(0 2px 3px rgba(0,0,0,.35)); }
    .__onda {
      position: fixed; z-index: 2147483646; pointer-events: none; width: 44px; height: 44px;
      margin: -22px 0 0 -22px; border-radius: 50%; background: rgba(255, 140, 0, .45);
      animation: __onda .55s ease-out forwards;
    }
    @keyframes __onda { from { transform: scale(.2); opacity: 1 } to { transform: scale(1.6); opacity: 0 } }
  `;
  document.head.appendChild(css);

  const c = document.createElement('div');
  c.id = '__cursore';
  c.innerHTML = `<svg width="26" height="26" viewBox="0 0 24 24"><path d="M4 2l15 11.5-6.6.9 3.8 7.4-2.9 1.5-3.8-7.5L4 20.5z" fill="#fff" stroke="#111" stroke-width="1.4" stroke-linejoin="round"/></svg>`;
  document.body.appendChild(c);

  addEventListener('mousemove', (e) => {
    c.style.transform = `translate(${e.clientX - 4}px, ${e.clientY - 2}px)`;
  }, true);
  addEventListener('mousedown', (e) => {
    const o = document.createElement('div');
    o.className = '__onda';
    o.style.left = `${e.clientX}px`;
    o.style.top = `${e.clientY}px`;
    document.body.appendChild(o);
    setTimeout(() => o.remove(), 700);
  }, true);
})();
