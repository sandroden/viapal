/* global React */

// Logo Viapal — versione "intarsio reale" (SVG vettorializzato dall'immagine
// di riferimento del mobile). L'immagine sta in viapal-logo-intarsio.svg.

function LogoIntarsio({ size = 200, mode = 'colore' }) {
  // mode: 'colore' (default), 'mono-scuro', 'mono-chiaro', 'silhouette'
  const filters = {
    'colore': 'none',
    'mono-scuro': 'grayscale(1) brightness(0.45) contrast(1.4)',
    'mono-chiaro': 'grayscale(1) brightness(1.6) contrast(0.9)',
    'silhouette': 'grayscale(1) brightness(0) contrast(1)',
  };
  return (
    <img
      src="viapal-logo-intarsio.svg"
      alt="Viapal logo"
      width={size}
      height={size}
      style={{
        display:'block',
        width:size,height:size,
        filter: filters[mode] || 'none',
      }}
    />
  );
}

function LogoIntarsioShowcase() {
  return (
    <div style={{width:'100%',height:'100%',padding:32,background:'var(--vp-paper)',color:'var(--vp-ink)',fontFamily:'var(--vp-font-ui)',overflow:'auto'}} className="vp-scroll">
      <div className="vp-eyebrow">Identità · intarsio reale</div>
      <h1 className="vp-display" style={{fontSize:38,margin:'4px 0 4px'}}>Il pappagallo del mobile, vettorizzato.</h1>
      <p style={{color:'var(--vp-ink-2)',fontSize:14,maxWidth:680,margin:'0 0 28px'}}>
        Questo è il file SVG vero, ricavato direttamente dall'immagine dell'intarsio. La palette (avena, miele, legno medio, legno scuro, salvia scura) è già coerente al 100% con Materica — non l'ho ricolorato.
      </p>

      {/* Hero */}
      <div className="vp-card" style={{padding:36,marginBottom:22,display:'grid',gridTemplateColumns:'auto 1fr',gap:36,alignItems:'center'}}>
        <div style={{
          width:340,height:340,
          background:'oklch(0.94 0.03 75)',
          borderRadius:64,
          display:'flex',alignItems:'center',justifyContent:'center',
          boxShadow:'var(--vp-shadow-3)',
          padding:14,
        }}>
          <LogoIntarsio size={300} mode="colore"/>
        </div>
        <div>
          <div className="vp-eyebrow">Marchio principale</div>
          <div className="vp-display" style={{fontSize:42,letterSpacing:'-0.01em',marginTop:4}}>Viapal</div>
          <div style={{fontFamily:'var(--vp-font-display)',fontSize:18,fontStyle:'italic',color:'var(--vp-ink-2)',marginTop:2}}>la casa, in tasca</div>
          <p style={{color:'var(--vp-ink-2)',fontSize:14,lineHeight:1.6,marginTop:18,maxWidth:380}}>
            Pappagallo di profilo + tetto a casetta + ramo con bacca. Il dettaglio dell'intarsio (le sfumature di legno) si legge nel grande; nel piccolo si fonde in silhouette ed è comunque riconoscibile.
          </p>
          <div style={{display:'flex',gap:8,marginTop:20,flexWrap:'wrap'}}>
            <span className="vp-chip" style={{background:'#e5dfc7',color:'#3e3b1f'}}>avena</span>
            <span className="vp-chip" style={{background:'#e0b277',color:'#3e3b1f'}}>miele</span>
            <span className="vp-chip" style={{background:'#b78548',color:'#fff'}}>legno chiaro</span>
            <span className="vp-chip" style={{background:'#8d5a2b',color:'#fff'}}>legno medio</span>
            <span className="vp-chip" style={{background:'#5b3b1c',color:'#fff'}}>legno scuro</span>
            <span className="vp-chip" style={{background:'#5f5930',color:'#fff'}}>salvia scura</span>
          </div>
        </div>
      </div>

      {/* 4 trattamenti */}
      <div className="vp-eyebrow" style={{marginBottom:14}}>Trattamenti</div>
      <div style={{display:'grid',gridTemplateColumns:'repeat(4,1fr)',gap:18,marginBottom:24}}>
        {[
          {label:'Colore (intarsio)', mode:'colore', bg:'oklch(0.94 0.03 75)'},
          {label:'Mono scuro',         mode:'silhouette', bg:'oklch(0.94 0.03 75)'},
          {label:'Reverse chiaro',     mode:'mono-chiaro', bg:'oklch(0.36 0.05 145)'},
          {label:'Mono terracotta',    mode:'silhouette', bg:'oklch(0.62 0.115 38)', tint:true},
        ].map(t => (
          <div key={t.label} className="vp-card" style={{padding:18}}>
            <div style={{
              aspectRatio:'1',borderRadius:22,overflow:'hidden',
              background:t.bg,
              display:'flex',alignItems:'center',justifyContent:'center',
              padding:14,marginBottom:14,
            }}>
              <div style={{filter: t.tint ? 'brightness(0) invert(0.95) sepia(0.2)' : undefined}}>
                <LogoIntarsio size={160} mode={t.mode}/>
              </div>
            </div>
            <div className="vp-display" style={{fontSize:16}}>{t.label}</div>
          </div>
        ))}
      </div>

      {/* Scala */}
      <div className="vp-eyebrow" style={{marginBottom:14}}>Prova della scala</div>
      <div className="vp-card" style={{padding:'28px 24px',marginBottom:24,display:'flex',alignItems:'flex-end',justifyContent:'center',gap:32,flexWrap:'wrap'}}>
        {[160,96,64,48,32,24,16].map(s => (
          <div key={s} style={{display:'flex',flexDirection:'column',alignItems:'center',gap:8}}>
            <div style={{
              width:s+12,height:s+12,borderRadius:Math.max(6,s*0.22),
              background:'oklch(0.94 0.03 75)',
              display:'flex',alignItems:'center',justifyContent:'center',
              padding:Math.max(2,s*0.06),
            }}>
              <LogoIntarsio size={s} mode="colore"/>
            </div>
            <div style={{fontSize:10,color:'var(--vp-ink-3)',fontFamily:'var(--vp-font-mono)'}}>{s}px</div>
          </div>
        ))}
      </div>

      {/* Lockup */}
      <div className="vp-eyebrow" style={{marginBottom:14}}>Lockup tipografico</div>
      <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:18,marginBottom:24}}>
        <div className="vp-card" style={{padding:'28px 32px',display:'flex',alignItems:'center',gap:20}}>
          <LogoIntarsio size={84} mode="colore"/>
          <div>
            <div style={{fontFamily:'var(--vp-font-display)',fontSize:42,letterSpacing:'-0.02em',lineHeight:1}}>Viapal</div>
            <div style={{fontFamily:'var(--vp-font-display)',fontSize:14,fontStyle:'italic',color:'var(--vp-ink-2)',marginTop:6}}>la casa, in tasca</div>
          </div>
        </div>
        <div style={{
          padding:'28px 32px',borderRadius:18,
          background:'oklch(0.36 0.05 145)',color:'oklch(0.94 0.03 75)',
          display:'flex',alignItems:'center',gap:20,
        }}>
          <div style={{
            width:84,height:84,
            background:'oklch(0.94 0.03 75)',
            borderRadius:18,padding:8,
            display:'flex',alignItems:'center',justifyContent:'center',
          }}>
            <LogoIntarsio size={68} mode="colore"/>
          </div>
          <div>
            <div style={{fontFamily:'var(--vp-font-display)',fontSize:42,letterSpacing:'-0.02em',lineHeight:1}}>Viapal</div>
            <div style={{fontFamily:'var(--vp-font-display)',fontSize:14,fontStyle:'italic',opacity:0.8,marginTop:6}}>la casa, in tasca</div>
          </div>
        </div>
      </div>

      {/* App icon mockup */}
      <div className="vp-eyebrow" style={{marginBottom:14}}>App icon (iOS)</div>
      <div style={{
        display:'grid',gridTemplateColumns:'repeat(4,1fr)',gap:18,
      }}>
        {[
          {bg:'oklch(0.94 0.03 75)',  label:'avena'},
          {bg:'oklch(0.62 0.115 38)', label:'terracotta'},
          {bg:'oklch(0.36 0.05 145)', label:'salvia scura'},
          {bg:'oklch(0.20 0.015 50)', label:'inchiostro'},
        ].map(t => (
          <div key={t.label} style={{display:'flex',flexDirection:'column',alignItems:'center',gap:10}}>
            <div style={{
              width:140,height:140,borderRadius:32,
              background:t.bg,
              display:'flex',alignItems:'center',justifyContent:'center',
              padding:10,
              boxShadow:'var(--vp-shadow-2)',
            }}>
              <LogoIntarsio size={120} mode="colore"/>
            </div>
            <div style={{fontSize:11,color:'var(--vp-ink-3)',fontFamily:'var(--vp-font-mono)'}}>{t.label}</div>
          </div>
        ))}
      </div>

      <div style={{
        marginTop:28,padding:'16px 20px',borderRadius:12,
        background:'var(--vp-paper-2)',fontSize:13,
        color:'var(--vp-ink-2)',lineHeight:1.5,
      }}>
        <b style={{color:'var(--vp-ink)'}}>Note pratiche:</b> il file vettoriale è in <code style={{fontFamily:'var(--vp-font-mono)',fontSize:12}}>viapal-logo-intarsio.svg</code> — pronto per favicon, app icon, materiali stampati. Su fondi chiari (avena/terracotta) la versione colore è la più narrativa; sotto i 32px o su fondi scuri passa alla silhouette.
      </div>
    </div>
  );
}

window.LogoIntarsio = LogoIntarsio;
window.LogoIntarsioShowcase = LogoIntarsioShowcase;
