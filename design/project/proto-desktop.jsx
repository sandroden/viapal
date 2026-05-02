/* global React, VPIcon, VPLeaf, VPHouse, VPAvatar, VPEnvelope */

// ── Prototipo 4: Calcolo conguaglio bollette (desktop) ────────
function ProtoConguaglio() {
  const [step, setStep] = React.useState(1); // 1: bolletta inserita, 2: ripartizione, 3: invio

  const inquilini = [
    { nome: 'Marco',  stanza: 'Salvia',  mq: 14, giorni: 92, persone: 1 },
    { nome: 'Sara',   stanza: 'Olmo',    mq: 18, giorni: 92, persone: 1 },
    { nome: 'Leila',  stanza: 'Tiglio',  mq: 12, giorni: 92, persone: 1 },
    { nome: 'Yusuf',  stanza: 'Acero',   mq: 16, giorni: 92, persone: 1 },
    { nome: 'Anna',   stanza: 'Ciliegio',mq: 15, giorni: 60, persone: 1 }, // entrata 1 ago
  ];
  const [criterio, setCriterio] = React.useState('teste'); // teste / mq / giorni
  const totale = 487.20;

  const quote = React.useMemo(() => {
    if (criterio === 'teste') {
      const q = totale / inquilini.length;
      return inquilini.map(i => ({ ...i, quota: q }));
    }
    if (criterio === 'mq') {
      const totMq = inquilini.reduce((s,i)=>s+i.mq,0);
      return inquilini.map(i => ({ ...i, quota: totale * i.mq / totMq }));
    }
    const totG = inquilini.reduce((s,i)=>s+i.giorni,0);
    return inquilini.map(i => ({ ...i, quota: totale * i.giorni / totG }));
  }, [criterio]);

  return (
    <div style={{width:'100%',height:'100%',overflow:'auto',background:'var(--vp-paper)',color:'var(--vp-ink)',fontFamily:'var(--vp-font-ui)'}} className="vp-scroll">
      {/* breadcrumb */}
      <div style={{padding:'18px 36px 0',display:'flex',alignItems:'center',gap:8,fontSize:13,color:'var(--vp-ink-3)'}}>
        <span>Bollette & conguagli</span>
        <VPIcon name="chevron" size={12}/>
        <span style={{color:'var(--vp-ink)'}}>Bolletta gas · estate 2026</span>
      </div>
      <div style={{padding:'12px 36px 36px',display:'grid',gridTemplateColumns:'1fr 380px',gap:28}}>
        <div>
          <h1 className="vp-display" style={{fontSize:32,margin:'8px 0 4px'}}>Conguaglio gas, <span style={{color:'var(--vp-ink-2)',fontStyle:'italic'}}>luglio–settembre</span></h1>
          <div style={{color:'var(--vp-ink-2)',fontSize:14,marginBottom:24}}>Bolletta arrivata il 2 ottobre. Da ripartire tra gli inquilini.</div>

          {/* Stepper */}
          <div style={{display:'flex',gap:10,marginBottom:22}}>
            {['Bolletta','Ripartizione','Invio'].map((l,i) => (
              <div key={i} style={{
                flex:1,padding:'10px 14px',borderRadius:10,
                background: i+1<=step?'var(--vp-cream)':'var(--vp-paper-2)',
                border:`1px solid ${i+1===step?'var(--vp-terra)':'var(--vp-paper-3)'}`,
                display:'flex',alignItems:'center',gap:10,
                color: i+1===step?'var(--vp-ink)':'var(--vp-ink-3)',
              }}>
                <div style={{
                  width:22,height:22,borderRadius:'50%',
                  background: i+1<step?'var(--vp-sage)':i+1===step?'var(--vp-terra)':'var(--vp-paper-3)',
                  color: i+1<=step?'#fff':'var(--vp-ink-3)',
                  display:'flex',alignItems:'center',justifyContent:'center',fontSize:12,fontWeight:600,
                }}>{i+1<step ? <VPIcon name="check" size={12} stroke={3} color="#fff"/> : i+1}</div>
                <span style={{fontSize:14,fontWeight:i+1===step?500:400}}>{l}</span>
              </div>
            ))}
          </div>

          {/* Bolletta block */}
          <div className="vp-card" style={{padding:'22px 24px',marginBottom:14}}>
            <div style={{display:'flex',gap:18,alignItems:'flex-start'}}>
              <div style={{
                width:88,height:114,background:'#f4ede1',borderRadius:6,
                padding:'8px 8px',transform:'rotate(-2deg)',
                fontFamily:'var(--vp-font-mono)',fontSize:7,color:'#3a2f24',
                boxShadow:'var(--vp-shadow-2)',flexShrink:0,
              }}>
                <div style={{fontWeight:700,fontSize:7}}>ENI · BOLLETTA</div>
                <div style={{borderBottom:'1px dashed #b8a784',margin:'3px 0'}}/>
                <div>Periodo: 01/07–30/09</div>
                <div>Consumo: 412 mc</div>
                <div>POD: 11AB02</div>
                <div style={{borderBottom:'1px dashed #b8a784',margin:'3px 0'}}/>
                <div style={{fontWeight:700,fontSize:9,textAlign:'right'}}>€ 487,20</div>
              </div>
              <div style={{flex:1}}>
                <div className="vp-eyebrow">Bolletta</div>
                <div className="vp-display" style={{fontSize:24,marginTop:4}}>Gas — luglio/agosto/settembre</div>
                <div style={{display:'flex',gap:24,marginTop:14,fontSize:14}}>
                  <Stat label="Totale" value="€ 487,20" big/>
                  <Stat label="Periodo" value="92 giorni"/>
                  <Stat label="Consumo" value="412 mc"/>
                  <Stat label="Fornitore" value="ENI"/>
                </div>
              </div>
            </div>
          </div>

          {/* Criterio */}
          <div className="vp-card" style={{padding:'22px 24px',marginBottom:14}}>
            <div style={{display:'flex',justifyContent:'space-between',alignItems:'baseline',marginBottom:14}}>
              <div className="vp-display" style={{fontSize:20}}>Come dividiamo?</div>
              <div style={{fontSize:13,color:'var(--vp-ink-3)'}}>Cambia il criterio, le quote si aggiornano.</div>
            </div>
            <div style={{display:'grid',gridTemplateColumns:'1fr 1fr 1fr',gap:10}}>
              {[
                ['teste','A testa','Tutti uguali','users'],
                ['mq','Per stanza','In base ai m²','home'],
                ['giorni','Pro-rata giorni','Solo i giorni in casa','clock'],
              ].map(([k,t,sub,ic]) => (
                <button key={k} onClick={()=>setCriterio(k)} style={{
                  padding:'14px 16px',borderRadius:12,cursor:'pointer',textAlign:'left',
                  background:criterio===k?'var(--vp-terra-soft)':'var(--vp-paper-2)',
                  border:`1.5px solid ${criterio===k?'var(--vp-terra)':'transparent'}`,
                  color:criterio===k?'var(--vp-terra-deep)':'var(--vp-ink)',
                  fontFamily:'inherit',
                }}>
                  <div style={{display:'flex',alignItems:'center',gap:8,marginBottom:4}}>
                    <VPIcon name={ic} size={16}/>
                    <span style={{fontSize:14,fontWeight:500}}>{t}</span>
                  </div>
                  <div style={{fontSize:12,color:criterio===k?'var(--vp-terra-deep)':'var(--vp-ink-3)'}}>{sub}</div>
                </button>
              ))}
            </div>
          </div>

          {/* Tabella ripartizione */}
          <div className="vp-card" style={{overflow:'hidden'}}>
            <div style={{padding:'18px 22px',display:'flex',justifyContent:'space-between',alignItems:'center'}}>
              <div className="vp-display" style={{fontSize:20}}>Ripartizione</div>
              <span style={{fontSize:13,color:'var(--vp-ink-3)'}}>somma: € {quote.reduce((s,q)=>s+q.quota,0).toFixed(2)}</span>
            </div>
            <table className="vp-table">
              <thead>
                <tr>
                  <th>Inquilino</th>
                  <th>Stanza</th>
                  <th style={{textAlign:'right'}}>m²</th>
                  <th style={{textAlign:'right'}}>Giorni</th>
                  <th style={{textAlign:'right'}}>Quota</th>
                </tr>
              </thead>
              <tbody>
                {quote.map((q,i)=>(
                  <tr key={i}>
                    <td>
                      <div style={{display:'flex',alignItems:'center',gap:10}}>
                        <VPAvatar name={q.nome} size={30} hue={20+i*30}/>
                        <span style={{fontWeight:500}}>{q.nome}</span>
                      </div>
                    </td>
                    <td style={{color:'var(--vp-ink-2)'}}>{q.stanza}</td>
                    <td style={{textAlign:'right'}} className="vp-mono">{q.mq}</td>
                    <td style={{textAlign:'right'}} className="vp-mono">{q.giorni}</td>
                    <td style={{textAlign:'right'}} className="vp-mono">
                      <span style={{fontWeight:500,fontSize:15}}>€ {q.quota.toFixed(2)}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Banner avviso anna */}
          <div className="vp-banner" style={{marginTop:14}}>
            <VPLeaf size={20}/>
            <div style={{flex:1}}>
              <b>Anna è entrata il 1° agosto.</b>{' '}
              <span style={{color:'var(--vp-ink-2)'}}>Con il criterio "pro-rata giorni" paga solo i 60 giorni in cui ha vissuto in casa.</span>
            </div>
          </div>
        </div>

        {/* RIGHT — anteprima messaggio */}
        <aside style={{position:'sticky',top:0,height:'fit-content',display:'flex',flexDirection:'column',gap:14}}>
          <div className="vp-card" style={{padding:'20px 22px'}}>
            <div className="vp-eyebrow">Anteprima invio</div>
            <div className="vp-display" style={{fontSize:18,marginTop:6,marginBottom:12}}>5 conguagli pronti</div>
            <div style={{
              background:'var(--vp-paper-2)',borderRadius:12,padding:14,
              fontSize:13,color:'var(--vp-ink-2)',lineHeight:1.5,marginBottom:14,
            }}>
              <div style={{color:'var(--vp-ink-3)',fontSize:11,letterSpacing:'0.04em',textTransform:'uppercase',marginBottom:6}}>Notifica push</div>
              "Ciao Marco 🌿 hai un conguaglio gas di <b>€ {quote[0].quota.toFixed(2)}</b> per i mesi luglio-settembre."
            </div>
            <button className="vp-btn vp-btn--primary" style={{width:'100%'}}>
              <VPEnvelope size={16}/> Invia 5 conguagli
            </button>
            <button className="vp-btn vp-btn--ghost" style={{width:'100%',marginTop:8}}>Salva in bozza</button>
          </div>

          <div style={{padding:'16px 18px',background:'var(--vp-paper-2)',borderRadius:14,fontSize:13,color:'var(--vp-ink-2)',lineHeight:1.5}}>
            <div style={{display:'flex',alignItems:'center',gap:8,color:'var(--vp-ink),fontWeight:500',marginBottom:6}}>
              <VPIcon name="clock" size={16}/>
              <b>Storico conguagli</b>
            </div>
            <div style={{display:'flex',justifyContent:'space-between',padding:'6px 0'}}><span>Inverno '25</span><span className="vp-mono">€ 612</span></div>
            <div style={{display:'flex',justifyContent:'space-between',padding:'6px 0'}}><span>Estate '25</span><span className="vp-mono">€ 392</span></div>
            <div style={{display:'flex',justifyContent:'space-between',padding:'6px 0'}}><span>Inverno '26</span><span className="vp-mono">€ 580</span></div>
          </div>
        </aside>
      </div>
    </div>
  );
}

function Stat({ label, value, big }) {
  return (
    <div>
      <div className="vp-eyebrow">{label}</div>
      <div className="vp-mono" style={{fontSize:big?22:15,fontWeight:big?500:400,marginTop:2,fontFamily:big?'var(--vp-font-display)':'var(--vp-font-ui)'}}>{value}</div>
    </div>
  );
}

window.ProtoConguaglio = ProtoConguaglio;


// ── Prototipo 5: Conti tra fratelli (desktop) ────────────────
function ProtoFratelli() {
  const fratelli = [
    { nome: 'Elena',  quota: 40, hue: 30 },
    { nome: 'Giulio', quota: 35, hue: 90 },
    { nome: 'Laura',  quota: 25, hue: 145 },
  ];
  const utiliAnno = 22450;

  const movimenti = [
    { who: 'Giulio', what: 'Idraulico (rubinetto cucina)', amount: 180, date: '12 set', tag: 'Manutenzione' },
    { who: 'Elena',  what: 'Assicurazione casa', amount: 340, date: '5 set', tag: 'Assicurazione' },
    { who: 'Laura',  what: 'IMU acconto', amount: 1200, date: '16 giu', tag: 'Tasse' },
    { who: 'Elena',  what: 'Bolletta condominio Q3', amount: 220, date: '28 ago', tag: 'Condominio' },
    { who: 'Giulio', what: 'Imbianchino corridoio', amount: 480, date: '4 lug', tag: 'Manutenzione' },
  ];

  // Saldi reciproci semplificati
  const saldi = [
    { from: 'Giulio', to: 'Elena',  amount: 124 },
    { from: 'Laura',  to: 'Elena',  amount: 86 },
  ];

  return (
    <div style={{width:'100%',height:'100%',overflow:'auto',background:'var(--vp-paper)',color:'var(--vp-ink)',fontFamily:'var(--vp-font-ui)'}} className="vp-scroll">
      <div style={{padding:'28px 40px 56px',maxWidth:1200,margin:'0 auto'}}>
        <div className="vp-eyebrow" style={{marginBottom:6}}>Conti tra fratelli · 2026</div>
        <h1 className="vp-display" style={{fontSize:36,margin:'0 0 6px'}}>Tutto torna, fratelli.</h1>
        <div style={{color:'var(--vp-ink-2)',fontSize:15,marginBottom:30}}>
          A oggi <b>4 ottobre</b>, ci sono <b>2 piccoli giroconti</b> da fare. Niente di che.
        </div>

        {/* Colonna 1+2 */}
        <div style={{display:'grid',gridTemplateColumns:'1.4fr 1fr',gap:22,marginBottom:22}}>
          {/* Quote di proprietà + utili */}
          <div className="vp-card" style={{padding:'24px 28px',position:'relative',overflow:'hidden'}}>
            <div className="vp-eyebrow">Utili 2026 da distribuire</div>
            <div className="vp-display" style={{fontSize:48,marginTop:6}}>€ {utiliAnno.toLocaleString('it-IT')}</div>
            <div style={{color:'var(--vp-ink-2)',fontSize:14,marginBottom:24}}>Affitti incassati − spese, dopo IMU.</div>

            {/* Barra orizzontale segmentata */}
            <div style={{display:'flex',height:14,borderRadius:'var(--vp-r-pill)',overflow:'hidden',marginBottom:18}}>
              {fratelli.map((f,i) => (
                <div key={i} style={{
                  width:`${f.quota}%`,
                  background:`oklch(0.68 0.08 ${f.hue})`,
                }}/>
              ))}
            </div>
            <div style={{display:'flex',justifyContent:'space-between',gap:20}}>
              {fratelli.map((f,i) => (
                <div key={i} style={{flex:1}}>
                  <div style={{display:'flex',alignItems:'center',gap:10,marginBottom:6}}>
                    <VPAvatar name={f.nome} size={32} hue={f.hue}/>
                    <div>
                      <div style={{fontSize:14,fontWeight:500}}>{f.nome}</div>
                      <div style={{fontSize:12,color:'var(--vp-ink-3)'}}>{f.quota}% di proprietà</div>
                    </div>
                  </div>
                  <div className="vp-mono" style={{fontSize:20,marginTop:8,fontFamily:'var(--vp-font-display)'}}>€ {Math.round(utiliAnno*f.quota/100).toLocaleString('it-IT')}</div>
                </div>
              ))}
            </div>
            <div style={{position:'absolute',right:-30,bottom:-30,opacity:0.06}}><VPHouse size={180}/></div>
          </div>

          {/* Saldi reciproci */}
          <div className="vp-card" style={{padding:'24px 28px'}}>
            <div className="vp-eyebrow">Giroconti consigliati</div>
            <div className="vp-display" style={{fontSize:22,marginTop:6,marginBottom:18}}>Chi deve cosa, oggi</div>

            <div style={{display:'flex',flexDirection:'column',gap:14}}>
              {saldi.map((s,i) => {
                const fromHue = fratelli.find(f=>f.nome===s.from).hue;
                const toHue = fratelli.find(f=>f.nome===s.to).hue;
                return (
                  <div key={i} style={{
                    display:'flex',alignItems:'center',gap:12,
                    padding:'14px 16px',borderRadius:14,
                    background:'var(--vp-paper-2)',
                  }}>
                    <VPAvatar name={s.from} size={36} hue={fromHue}/>
                    <div style={{flex:1,display:'flex',alignItems:'center',gap:10}}>
                      <span style={{fontSize:14,fontWeight:500}}>{s.from}</span>
                      <VPIcon name="arrow" size={16} color="var(--vp-ink-3)"/>
                      <span style={{fontSize:14,fontWeight:500}}>{s.to}</span>
                    </div>
                    <VPAvatar name={s.to} size={36} hue={toHue}/>
                    <div className="vp-mono" style={{fontSize:18,fontFamily:'var(--vp-font-display)'}}>€ {s.amount}</div>
                  </div>
                );
              })}
            </div>
            <button className="vp-btn vp-btn--primary" style={{width:'100%',marginTop:18}}>
              Segna come saldato
            </button>
            <div style={{marginTop:14,fontSize:13,color:'var(--vp-ink-3)',textAlign:'center'}}>
              Ultimo conguaglio: <b style={{color:'var(--vp-ink-2)'}}>30 giugno '26</b>
            </div>
          </div>
        </div>

        {/* Movimenti recenti */}
        <div className="vp-card" style={{overflow:'hidden'}}>
          <div style={{padding:'18px 22px',display:'flex',justifyContent:'space-between',alignItems:'center'}}>
            <div>
              <div className="vp-display" style={{fontSize:20}}>Spese anticipate dai fratelli</div>
              <div style={{fontSize:13,color:'var(--vp-ink-3)',marginTop:2}}>Verranno scalate dagli utili o saldate a fine anno.</div>
            </div>
            <button className="vp-btn vp-btn--ghost"><VPIcon name="plus" size={14}/>Aggiungi</button>
          </div>
          <table className="vp-table">
            <thead>
              <tr>
                <th>Anticipato da</th>
                <th>Spesa</th>
                <th>Categoria</th>
                <th>Data</th>
                <th style={{textAlign:'right'}}>Importo</th>
              </tr>
            </thead>
            <tbody>
              {movimenti.map((m,i)=>{
                const hue = fratelli.find(f=>f.nome===m.who)?.hue || 30;
                return (
                  <tr key={i}>
                    <td>
                      <div style={{display:'flex',alignItems:'center',gap:10}}>
                        <VPAvatar name={m.who} size={28} hue={hue}/>
                        <span style={{fontWeight:500}}>{m.who}</span>
                      </div>
                    </td>
                    <td>{m.what}</td>
                    <td><span className="vp-badge vp-badge--neutral">{m.tag}</span></td>
                    <td style={{color:'var(--vp-ink-3)'}}>{m.date}</td>
                    <td style={{textAlign:'right'}} className="vp-mono">€ {m.amount.toLocaleString('it-IT')}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

window.ProtoFratelli = ProtoFratelli;
