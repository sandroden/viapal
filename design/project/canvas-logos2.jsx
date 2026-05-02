/* global React, LogoD, LogoE, LogoF */

function LogoExploration2() {
  return (
    <div style={{width:'100%',height:'100%',padding:32,background:'var(--vp-paper)',color:'var(--vp-ink)',fontFamily:'var(--vp-font-ui)',overflow:'auto'}} className="vp-scroll">
      <div className="vp-eyebrow">Identità · pappagallo nella casa</div>
      <h1 className="vp-display" style={{fontSize:38,margin:'4px 0 4px'}}>Pappagallo + casa + ramo.</h1>
      <p style={{color:'var(--vp-ink-2)',fontSize:14,maxWidth:680,margin:'0 0 28px'}}>
        Stessa idea della direzione che mi hai mandato: silhouette di pappagallo (testa di profilo, occhio, becco) dentro il profilo di una casa, con un piccolo ramo+bacca. Riprodotta in SVG pulito, scalabile, senza dipendenze AI.
      </p>

      {/* Hero — versione grande */}
      <div className="vp-card" style={{padding:36,marginBottom:22,display:'grid',gridTemplateColumns:'auto 1fr',gap:36,alignItems:'center'}}>
        <div style={{
          width:280,height:280,background:'oklch(0.94 0.03 75)',
          borderRadius:56,display:'flex',alignItems:'center',justifyContent:'center',
          boxShadow:'var(--vp-shadow-3)',
        }}>
          <LogoD size={240} bg={null} bird="oklch(0.52 0.08 40)" accent="oklch(0.50 0.07 145)" stroke="oklch(0.30 0.04 40)"/>
        </div>
        <div>
          <div className="vp-eyebrow">Direzione D · scelta consigliata</div>
          <div className="vp-display" style={{fontSize:42,letterSpacing:'-0.01em',marginTop:4}}>Viapal</div>
          <div style={{fontFamily:'var(--vp-font-display)',fontSize:18,fontStyle:'italic',color:'var(--vp-ink-2)',marginTop:2}}>la casa, in tasca</div>
          <p style={{color:'var(--vp-ink-2)',fontSize:14,lineHeight:1.6,marginTop:18,maxWidth:380}}>
            Il <b>pappagallo dell'intarsio</b> diventa il volto dell'app. La <b>casa</b> lo abbraccia. Il <b>ramo con bacca</b> richiama le fronde del mobile e fa da "gioiello" — è il dettaglio caldo che evita la freddezza da pittogramma.
          </p>
        </div>
      </div>

      {/* 3 trattamenti × 3 fondi */}
      <div className="vp-eyebrow" style={{marginBottom:14}}>Tre trattamenti</div>
      <div style={{display:'grid',gridTemplateColumns:'1fr 1fr 1fr',gap:18,marginBottom:24}}>
        <div className="vp-card" style={{padding:18}}>
          <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:10,marginBottom:14}}>
            <div style={{aspectRatio:'1',borderRadius:22,overflow:'hidden'}}>
              <LogoD size={160} bg="oklch(0.94 0.03 75)" bird="oklch(0.52 0.08 40)" accent="oklch(0.50 0.07 145)" stroke="oklch(0.30 0.04 40)"/>
            </div>
            <div style={{aspectRatio:'1',borderRadius:22,overflow:'hidden'}}>
              <LogoD size={160} bg="oklch(0.62 0.115 38)" bird="oklch(0.92 0.04 70)" accent="oklch(0.85 0.06 145)" stroke="oklch(0.92 0.04 70)"/>
            </div>
          </div>
          <div className="vp-display" style={{fontSize:18}}>D · Pieno (intarsio)</div>
          <div style={{fontSize:13,color:'var(--vp-ink-2)',marginTop:4,lineHeight:1.5}}>Più ricco e narrativo. Dentro c'è il petto chiaro, becco color miele. Funziona sopra i 32px.</div>
        </div>

        <div className="vp-card" style={{padding:18}}>
          <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:10,marginBottom:14}}>
            <div style={{aspectRatio:'1',borderRadius:22,overflow:'hidden'}}>
              <LogoE size={160} bg="oklch(0.94 0.03 75)" color="oklch(0.30 0.04 40)" accent="oklch(0.50 0.07 145)"/>
            </div>
            <div style={{aspectRatio:'1',borderRadius:22,overflow:'hidden'}}>
              <LogoE size={160} bg="oklch(0.97 0.01 80)" color="oklch(0.55 0.08 40)" accent="oklch(0.55 0.07 145)"/>
            </div>
          </div>
          <div className="vp-display" style={{fontSize:18}}>E · Stencil</div>
          <div style={{fontSize:13,color:'var(--vp-ink-2)',marginTop:4,lineHeight:1.5}}>Casa stroke, pappagallo solido. Più "marchio". Scala benissimo a 24px e sotto.</div>
        </div>

        <div className="vp-card" style={{padding:18}}>
          <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:10,marginBottom:14}}>
            <div style={{aspectRatio:'1',borderRadius:22,overflow:'hidden'}}>
              <LogoF size={160} bg="oklch(0.36 0.05 145)" fg="oklch(0.94 0.03 75)"/>
            </div>
            <div style={{aspectRatio:'1',borderRadius:22,overflow:'hidden'}}>
              <LogoF size={160} bg="oklch(0.26 0.022 50)" fg="oklch(0.78 0.10 75)"/>
            </div>
          </div>
          <div className="vp-display" style={{fontSize:18}}>F · Reverse</div>
          <div style={{fontSize:13,color:'var(--vp-ink-2)',marginTop:4,lineHeight:1.5}}>Mono su scuro per dark mode, splash notturno, pin notifiche.</div>
        </div>
      </div>

      {/* Scala */}
      <div className="vp-eyebrow" style={{marginBottom:14}}>Prova della scala</div>
      <div className="vp-card" style={{padding:'22px 24px',marginBottom:24,display:'flex',alignItems:'flex-end',justifyContent:'center',gap:36}}>
        {[120,72,48,32,24,16].map(s => (
          <div key={s} style={{display:'flex',flexDirection:'column',alignItems:'center',gap:8}}>
            <div style={{
              width:s+12,height:s+12,borderRadius:s*0.22+4,
              background:'oklch(0.62 0.115 38)',
              display:'flex',alignItems:'center',justifyContent:'center',
            }}>
              <LogoD size={s} bg={null} bird="oklch(0.92 0.04 70)" accent="oklch(0.85 0.06 145)" stroke="oklch(0.92 0.04 70)" frame={true}/>
            </div>
            <div style={{fontSize:10,color:'var(--vp-ink-3)',fontFamily:'var(--vp-font-mono)'}}>{s}px</div>
          </div>
        ))}
      </div>

      {/* Lockup */}
      <div className="vp-eyebrow" style={{marginBottom:14}}>Lockup</div>
      <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:18}}>
        <div className="vp-card" style={{padding:'24px 28px',display:'flex',alignItems:'center',gap:18}}>
          <LogoE size={64} color="var(--vp-ink)" accent="var(--vp-leaf)"/>
          <div>
            <div style={{fontFamily:'var(--vp-font-display)',fontSize:36,letterSpacing:'-0.02em',lineHeight:1}}>Viapal</div>
            <div style={{fontFamily:'var(--vp-font-display)',fontSize:14,fontStyle:'italic',color:'var(--vp-ink-2)',marginTop:4}}>la casa, in tasca</div>
          </div>
        </div>
        <div style={{
          padding:'24px 28px',borderRadius:18,
          background:'oklch(0.36 0.05 145)',color:'oklch(0.94 0.03 75)',
          display:'flex',alignItems:'center',gap:18,
        }}>
          <LogoF size={64} bg="oklch(0.36 0.05 145)" fg="oklch(0.94 0.03 75)"/>
          <div>
            <div style={{fontFamily:'var(--vp-font-display)',fontSize:36,letterSpacing:'-0.02em',lineHeight:1}}>Viapal</div>
            <div style={{fontFamily:'var(--vp-font-display)',fontSize:14,fontStyle:'italic',opacity:0.8,marginTop:4}}>la casa, in tasca</div>
          </div>
        </div>
      </div>

      <div style={{
        marginTop:28,padding:'16px 20px',borderRadius:12,
        background:'var(--vp-paper-2)',fontSize:13,
        color:'var(--vp-ink-2)',lineHeight:1.5,
      }}>
        <b style={{color:'var(--vp-ink)'}}>Come si comporta in scala:</b> sopra i 32px tieni la versione D (pieno, con petto chiaro e becco miele). Sotto i 32px passa alla E (stencil) — il pappagallo resta riconoscibile, il ramo si semplifica. La F è solo per superfici scure.
      </div>
    </div>
  );
}

window.LogoExploration2 = LogoExploration2;
