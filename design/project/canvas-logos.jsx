/* global React, LogoA, LogoB, LogoC */

function LogoExploration() {
  const variants = [
    { id: 'A', Cmp: LogoA, name: 'Linea continua', sub: 'La più fedele all\'intarsio: pappagallo + arcata + ramo come un timbro/ex-libris. Calda, narrativa.' },
    { id: 'B', Cmp: LogoB, name: 'Geometrico', sub: 'Forme primarie — corpo a goccia, 3 strisce di coda. Moderno, scala bene da 24px in su.' },
    { id: 'C', Cmp: LogoC, name: 'Astratto · V foglia', sub: 'La V di Viapal con foglia interna. Più "serio", funziona anche a 16px come favicon.' },
  ];

  return (
    <div style={{
      width:'100%', height:'100%', padding: 32,
      background: 'var(--vp-paper)', color: 'var(--vp-ink)',
      fontFamily: 'var(--vp-font-ui)', overflow: 'auto',
    }} className="vp-scroll">
      <div className="vp-eyebrow">Identità · logo dall'intarsio</div>
      <h1 className="vp-display" style={{fontSize: 38, margin: '4px 0 4px'}}>Il pappagallo del mobile, stilizzato.</h1>
      <p style={{color:'var(--vp-ink-2)', fontSize: 14, maxWidth: 680, margin: '0 0 28px'}}>
        Tre livelli di astrazione, dallo stesso intarsio: arcata, pappagallo, fronde, fiore. Da provinare in scala — la prova del 24px è quella che conta.
      </p>

      <div style={{display:'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 22}}>
        {variants.map(({ id, Cmp, name, sub }) => (
          <div key={id} className="vp-card" style={{padding: 22, display:'flex', flexDirection:'column', gap: 16, alignItems:'stretch'}}>
            {/* big stamp */}
            <div style={{
              aspectRatio: '1', background: 'var(--vp-paper-2)', borderRadius: 14,
              display:'flex', alignItems:'center', justifyContent:'center',
            }}>
              <Cmp size={200}/>
            </div>

            {/* su sfondo terracotta (icona PWA) */}
            <div style={{display:'flex', gap: 10}}>
              <div style={{
                flex:1, aspectRatio:'1', borderRadius: 22,
                background: 'oklch(0.62 0.115 38)',
                display:'flex', alignItems:'center', justifyContent:'center',
                boxShadow: 'var(--vp-shadow-2)',
              }}>
                <Cmp size={84} color="oklch(0.96 0.04 70)" accent="oklch(0.85 0.06 145)"/>
              </div>
              <div style={{
                flex:1, aspectRatio:'1', borderRadius: 22,
                background: 'oklch(0.30 0.025 50)',
                display:'flex', alignItems:'center', justifyContent:'center',
              }}>
                <Cmp size={84} color="oklch(0.85 0.06 40)" accent="oklch(0.78 0.08 145)"/>
              </div>
              <div style={{
                flex:1, aspectRatio:'1', borderRadius: 22,
                background: 'var(--vp-cream)', border: '1px solid var(--vp-paper-3)',
                display:'flex', alignItems:'center', justifyContent:'center',
              }}>
                <Cmp size={84}/>
              </div>
            </div>

            {/* size scale */}
            <div style={{
              display:'flex', alignItems:'flex-end', justifyContent:'center', gap: 14,
              padding: '10px 4px',
              background: 'var(--vp-paper-2)', borderRadius: 10,
            }}>
              {[64, 40, 24, 16].map(s => (
                <div key={s} style={{display:'flex', flexDirection:'column', alignItems:'center', gap: 4}}>
                  <Cmp size={s}/>
                  <div style={{fontSize: 9, color:'var(--vp-ink-3)', fontFamily:'var(--vp-font-mono)'}}>{s}px</div>
                </div>
              ))}
            </div>

            {/* lockup tipografico */}
            <div style={{
              display:'flex', alignItems:'center', gap: 10,
              padding: '10px 14px',
              background: 'var(--vp-cream)', border: '1px solid var(--vp-paper-3)',
              borderRadius: 10,
            }}>
              <Cmp size={32}/>
              <div style={{fontFamily:'var(--vp-font-display)', fontSize: 22, letterSpacing:'-0.01em'}}>Viapal</div>
              <div style={{flex:1}}/>
              <div style={{fontSize: 11, color:'var(--vp-ink-3)', fontStyle:'italic', fontFamily:'var(--vp-font-display)'}}>la casa, in tasca</div>
            </div>

            <div>
              <div className="vp-display" style={{fontSize: 20}}>Opzione {id} — {name}</div>
              <div style={{fontSize: 13, color:'var(--vp-ink-2)', lineHeight: 1.5, marginTop: 4}}>{sub}</div>
            </div>
          </div>
        ))}
      </div>

      <div style={{
        marginTop: 28, padding: '16px 20px',
        borderRadius: 12, background: 'var(--vp-paper-2)',
        fontSize: 13, color: 'var(--vp-ink-2)', lineHeight: 1.5,
      }}>
        <b style={{color:'var(--vp-ink)'}}>Suggerimento:</b> A è bellissimo per stamperia (carta intestata, ricevute fisiche), ma a 24px diventa rumoroso. C scala a tutto. B è il compromesso che terrei come marchio principale, con A come "sigillo" decorativo nei punti caldi (mail di benvenuto, splash).
      </div>
    </div>
  );
}

window.LogoExploration = LogoExploration;
