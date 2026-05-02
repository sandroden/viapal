/* global React, VPIcon, VPLeaf, VPEnvelope, VPHouse, VPAvatar, VPRoof */

// ── Prototipo 1: Dashboard rendita (desktop) ─────────────────
// Stato: simulazione di gestione mensile (ottobre)
// Interazioni: hover righe, click "approva", click "sollecita", click mese

function ProtoDashboard() {
  const [month, setMonth] = React.useState(9); // ottobre = 9
  const months = ['Gen','Feb','Mar','Apr','Mag','Giu','Lug','Ago','Set','Ott','Nov','Dic'];

  const inquilini = [
    { nome: 'Marco', stanza: 'Salvia',  affitto: 480, status: 'late', giorni: 3 },
    { nome: 'Sara',  stanza: 'Olmo',    affitto: 520, status: 'ok',   data: '2 ott' },
    { nome: 'Leila', stanza: 'Tiglio',  affitto: 460, status: 'ok',   data: '1 ott' },
    { nome: 'Yusuf', stanza: 'Acero',   affitto: 540, status: 'wait', giorni: 1 },
    { nome: 'Anna',  stanza: 'Ciliegio',affitto: 500, status: 'ok',   data: '3 ott' },
  ];

  const totaleAtteso = inquilini.reduce((s,i) => s + i.affitto, 0);
  const totaleIncassato = inquilini.filter(i => i.status==='ok').reduce((s,i)=>s+i.affitto,0);
  const pct = Math.round(totaleIncassato / totaleAtteso * 100);

  // grafico incassi vs uscite (12 mesi finti)
  const chartData = [
    {in: 2380, out: 320}, {in: 2500, out: 410}, {in: 2500, out: 280},
    {in: 2500, out: 690}, {in: 2500, out: 340}, {in: 2500, out: 290},
    {in: 2500, out: 520}, {in: 2500, out: 180}, {in: 2500, out: 410},
    {in: totaleIncassato, out: 380}, {in: 0, out: 0}, {in: 0, out: 0},
  ];
  const max = 3000;

  const Pill = ({status, giorni, data}) => {
    if (status === 'ok')   return <span className="vp-badge vp-badge--ok"><span className="vp-dot vp-dot--ok"/>Ricevuto · {data}</span>;
    if (status === 'wait') return <span className="vp-badge vp-badge--wait"><span className="vp-dot vp-dot--wait"/>Da approvare</span>;
    return <span className="vp-badge vp-badge--late"><span className="vp-dot vp-dot--late"/>In ritardo · {giorni}g</span>;
  };

  return (
    <div style={{
      width: '100%', height: '100%', overflow: 'auto',
      background: 'var(--vp-paper)', color: 'var(--vp-ink)',
      fontFamily: 'var(--vp-font-ui)',
    }} className="vp-scroll">
      {/* Sidebar + main */}
      <div style={{ display: 'grid', gridTemplateColumns: '232px 1fr', minHeight: '100%' }}>
        {/* SIDEBAR */}
        <aside style={{
          background: 'var(--vp-paper-2)',
          borderRight: '1px solid var(--vp-paper-3)',
          padding: '24px 16px', display: 'flex', flexDirection: 'column', gap: 4,
        }}>
          <div style={{display:'flex',alignItems:'center',gap:10,padding:'8px 10px 18px'}}>
            <div style={{width:32,height:32,borderRadius:8,background:'var(--vp-terra)',display:'flex',alignItems:'center',justifyContent:'center',color:'var(--vp-cream)',fontFamily:'var(--vp-font-display)',fontSize:18,fontWeight:500}}>V</div>
            <div>
              <div style={{fontFamily:'var(--vp-font-display)',fontSize:18,fontWeight:500}}>Viapal</div>
              <div style={{fontSize:11,color:'var(--vp-ink-3)'}}>Via Palestrina 12</div>
            </div>
          </div>
          {[
            ['home','Rendita',true],
            ['users','Inquilini'],
            ['wallet','Pagamenti affitto'],
            ['bills','Bollette & conguagli'],
            ['receipt','Spese generali'],
            ['wrench','Manutenzioni'],
            ['users','Conti tra fratelli'],
            ['folder','Documenti'],
            ['chart','Reportistica'],
            ['settings','Configurazione'],
          ].map(([icon, label, active]) => (
            <div key={label} style={{
              display:'flex',alignItems:'center',gap:12,
              padding:'9px 10px',borderRadius:8,
              background: active ? 'var(--vp-cream)' : 'transparent',
              boxShadow: active ? 'var(--vp-shadow-1)' : 'none',
              color: active ? 'var(--vp-ink)' : 'var(--vp-ink-2)',
              fontSize:14, fontWeight: active?500:400,
              cursor:'pointer',
            }}>
              <VPIcon name={icon} size={17} stroke={active?1.8:1.5}/>
              {label}
            </div>
          ))}
          <div style={{flex:1}}/>
          <div style={{
            padding:14, borderRadius:12, background:'var(--vp-cream)',
            border:'1px dashed var(--vp-paper-3)', fontSize:12, color:'var(--vp-ink-2)',
            display:'flex', gap:10, alignItems:'flex-start',
          }}>
            <VPLeaf size={28}/>
            <div>
              <div style={{fontWeight:500,color:'var(--vp-ink)',marginBottom:2}}>Ottobre tranquillo</div>
              4 su 5 hanno già pagato. Manca solo Marco.
            </div>
          </div>
        </aside>

        {/* MAIN */}
        <main style={{ padding: '28px 36px 56px', display:'flex', flexDirection:'column', gap: 24 }}>
          {/* topbar */}
          <header style={{display:'flex',alignItems:'center',justifyContent:'space-between'}}>
            <div>
              <div className="vp-eyebrow" style={{marginBottom:6}}>Buongiorno, Elena</div>
              <h1 className="vp-display" style={{fontSize:34,margin:0}}>
                Casa di Via Palestrina, <span style={{color:'var(--vp-ink-2)',fontStyle:'italic'}}>ottobre</span>
              </h1>
            </div>
            <div style={{display:'flex',gap:10,alignItems:'center'}}>
              <button className="vp-btn vp-btn--ghost"><VPIcon name="download" size={16}/>Export</button>
              <button className="vp-btn vp-btn--primary"><VPIcon name="plus" size={16}/>Nuova spesa</button>
            </div>
          </header>

          {/* KPI tiles */}
          <div style={{display:'grid',gridTemplateColumns:'1.4fr 1fr 1fr 1fr',gap:14}}>
            {/* Big tile: incassi mese */}
            <div className="vp-card" style={{padding:'22px 24px',position:'relative',overflow:'hidden'}}>
              <div className="vp-eyebrow">Incassi {months[month]}</div>
              <div className="vp-display" style={{fontSize:44,marginTop:8}}>
                € <span style={{fontVariantNumeric:'tabular-nums'}}>{totaleIncassato.toLocaleString('it-IT')}</span>
                <span style={{color:'var(--vp-ink-3)',fontSize:24}}> / {totaleAtteso.toLocaleString('it-IT')}</span>
              </div>
              <div style={{display:'flex',alignItems:'center',gap:10,marginTop:14}}>
                <div style={{flex:1,height:8,background:'var(--vp-paper-3)',borderRadius:4,overflow:'hidden'}}>
                  <div style={{width:`${pct}%`,height:'100%',background:'var(--vp-sage)'}}/>
                </div>
                <span style={{fontSize:13,color:'var(--vp-ink-2)'}} className="vp-mono">{pct}%</span>
              </div>
              <div style={{position:'absolute',right:-10,top:-10,opacity:0.10}}><VPHouse size={120}/></div>
            </div>

            <div className="vp-card" style={{padding:'18px 20px'}}>
              <div className="vp-eyebrow">Margine annuo</div>
              <div className="vp-display" style={{fontSize:30,marginTop:8}}>€ 22.450</div>
              <div style={{display:'flex',alignItems:'center',gap:6,fontSize:13,color:'var(--vp-sage-deep)',marginTop:6}}>
                <VPIcon name="trend" size={14}/> +4,2% vs 2025
              </div>
            </div>
            <div className="vp-card" style={{padding:'18px 20px'}}>
              <div className="vp-eyebrow">Spese ottobre</div>
              <div className="vp-display" style={{fontSize:30,marginTop:8}}>€ 380</div>
              <div style={{fontSize:13,color:'var(--vp-ink-3)',marginTop:6}}>Bolletta gas, idraulico</div>
            </div>
            <div className="vp-card" style={{padding:'18px 20px',background:'var(--vp-clay-soft)'}}>
              <div className="vp-eyebrow" style={{color:'oklch(0.40 0.10 28)'}}>Da sollecitare</div>
              <div className="vp-display" style={{fontSize:30,marginTop:8,color:'oklch(0.35 0.11 28)'}}>1 inquilino</div>
              <div style={{fontSize:13,color:'oklch(0.40 0.10 28)',marginTop:6,display:'flex',alignItems:'center',gap:6}}>
                <VPIcon name="alert" size={14}/> Marco · 3 giorni
              </div>
            </div>
          </div>

          {/* Banner sollecito */}
          <div className="vp-banner vp-banner--late">
            <VPIcon name="bell" size={18} style={{marginTop:2,color:'var(--vp-clay)'}}/>
            <div style={{flex:1}}>
              <div style={{fontWeight:500,marginBottom:2}}>Manca ancora la ricevuta di Marco 🌿</div>
              <div style={{color:'var(--vp-ink-2)',fontSize:13}}>L'affitto di ottobre non è ancora arrivato. Di solito paga il 1°.</div>
            </div>
            <button className="vp-btn vp-btn--ghost" style={{height:34}}>Scrivi a Marco</button>
            <button className="vp-btn vp-btn--primary" style={{height:34}}>Manda sollecito</button>
          </div>

          {/* Tabella stato pagamenti */}
          <div className="vp-card" style={{overflow:'hidden'}}>
            <div style={{padding:'18px 22px',display:'flex',justifyContent:'space-between',alignItems:'center'}}>
              <div>
                <div className="vp-display" style={{fontSize:20}}>Pagamenti affitto · {months[month]}</div>
                <div style={{fontSize:13,color:'var(--vp-ink-3)',marginTop:2}}>Tocca un nome per il dettaglio</div>
              </div>
              <div style={{display:'flex',gap:6,padding:4,background:'var(--vp-paper-2)',borderRadius:'var(--vp-r-pill)'}}>
                {months.map((m,i) => (
                  <button key={i} onClick={()=>setMonth(i)} style={{
                    border:'none',background: i===month?'var(--vp-cream)':'transparent',
                    color: i===month?'var(--vp-ink)':'var(--vp-ink-3)',
                    padding:'6px 10px',borderRadius:'var(--vp-r-pill)',
                    fontSize:12,fontWeight:i===month?500:400,cursor:'pointer',
                    boxShadow:i===month?'var(--vp-shadow-1)':'none',
                  }}>{m}</button>
                ))}
              </div>
            </div>
            <table className="vp-table">
              <thead>
                <tr>
                  <th>Inquilino</th>
                  <th>Stanza</th>
                  <th style={{textAlign:'right'}}>Affitto</th>
                  <th>Stato</th>
                  <th style={{width:140}}/>
                </tr>
              </thead>
              <tbody>
                {inquilini.map((i,k) => (
                  <tr key={k}>
                    <td>
                      <div style={{display:'flex',alignItems:'center',gap:10}}>
                        <VPAvatar name={i.nome} size={32} hue={20+k*30}/>
                        <span style={{fontWeight:500}}>{i.nome}</span>
                      </div>
                    </td>
                    <td style={{color:'var(--vp-ink-2)'}}>{i.stanza}</td>
                    <td style={{textAlign:'right'}} className="vp-mono">€ {i.affitto}</td>
                    <td><Pill {...i}/></td>
                    <td style={{textAlign:'right'}}>
                      {i.status==='wait' && <button className="vp-btn vp-btn--soft" style={{height:30,fontSize:13}}>Approva</button>}
                      {i.status==='late' && <button className="vp-btn vp-btn--ghost" style={{height:30,fontSize:13}}>Sollecita</button>}
                      {i.status==='ok' && <span style={{color:'var(--vp-ink-4)',fontSize:13}}>—</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Grafico + scadenze */}
          <div style={{display:'grid',gridTemplateColumns:'1.6fr 1fr',gap:14}}>
            <div className="vp-card" style={{padding:'22px 24px'}}>
              <div style={{display:'flex',justifyContent:'space-between',alignItems:'baseline',marginBottom:18}}>
                <div className="vp-display" style={{fontSize:20}}>Incassi e uscite, 12 mesi</div>
                <div style={{display:'flex',gap:14,fontSize:12,color:'var(--vp-ink-2)'}}>
                  <span style={{display:'flex',alignItems:'center',gap:6}}><span className="vp-dot" style={{background:'var(--vp-sage)'}}/>Incassi</span>
                  <span style={{display:'flex',alignItems:'center',gap:6}}><span className="vp-dot" style={{background:'var(--vp-clay)'}}/>Uscite</span>
                </div>
              </div>
              <div style={{display:'flex',alignItems:'flex-end',gap:10,height:160}}>
                {chartData.map((d,i) => (
                  <div key={i} style={{flex:1,display:'flex',flexDirection:'column',alignItems:'center',gap:4}}>
                    <div style={{display:'flex',alignItems:'flex-end',gap:3,height:140,width:'100%',justifyContent:'center'}}>
                      <div style={{
                        width:'40%',background:'var(--vp-sage)',borderRadius:'4px 4px 0 0',
                        height:`${d.in/max*100}%`, opacity: i===month?1:0.5, transition:'opacity .2s',
                      }}/>
                      <div style={{
                        width:'40%',background:'var(--vp-clay)',borderRadius:'4px 4px 0 0',
                        height:`${d.out/max*100}%`, opacity: i===month?1:0.4,
                      }}/>
                    </div>
                    <div style={{fontSize:11,color:i===month?'var(--vp-ink)':'var(--vp-ink-3)',fontWeight:i===month?500:400}}>{months[i]}</div>
                  </div>
                ))}
              </div>
            </div>
            <div className="vp-card" style={{padding:'22px 24px'}}>
              <div className="vp-display" style={{fontSize:20,marginBottom:14}}>Prossime scadenze</div>
              <div style={{display:'flex',flexDirection:'column',gap:14}}>
                {[
                  {icon:'flame',label:'Bolletta gas',date:'15 ott',amount:'€ 240'},
                  {icon:'drop',label:'Bolletta acqua',date:'22 ott',amount:'€ 95'},
                  {icon:'doc',label:'IMU acconto',date:'16 dic',amount:'€ 1.200'},
                  {icon:'contract',label:'Rinnovo contratto Sara',date:'30 nov',amount:''},
                ].map((s,i) => (
                  <div key={i} style={{display:'flex',alignItems:'center',gap:12}}>
                    <div style={{width:36,height:36,borderRadius:10,background:'var(--vp-paper-2)',display:'flex',alignItems:'center',justifyContent:'center',color:'var(--vp-terra)'}}>
                      <VPIcon name={s.icon} size={18}/>
                    </div>
                    <div style={{flex:1}}>
                      <div style={{fontSize:14,fontWeight:500}}>{s.label}</div>
                      <div style={{fontSize:12,color:'var(--vp-ink-3)'}}>{s.date}</div>
                    </div>
                    {s.amount && <div className="vp-mono" style={{fontSize:14,color:'var(--vp-ink-2)'}}>{s.amount}</div>}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}

window.ProtoDashboard = ProtoDashboard;
