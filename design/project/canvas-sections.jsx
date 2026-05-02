/* global React, VPIcon, VPLeaf, VPHouse, VPEnvelope, VPRoof, VPAvatar */

// ────────────────────────────────────────────────────────
// Moodboard — direzione "Materica" (scelta) + alternativa "Block organizer"
// ────────────────────────────────────────────────────────

function MoodMaterica() {
  return (
    <div style={{
      width:'100%',height:'100%',padding:32,
      background:'var(--vp-paper)',
      fontFamily:'var(--vp-font-ui)',color:'var(--vp-ink)',
      display:'grid',gridTemplateColumns:'1.1fr 0.9fr',gap:24,
    }}>
      <div style={{display:'flex',flexDirection:'column',gap:18}}>
        <div>
          <div className="vp-eyebrow" style={{color:'var(--vp-terra)'}}>Direzione 1 · Scelta</div>
          <h1 className="vp-display" style={{fontSize:54,margin:'4px 0 8px',lineHeight:0.95}}>Materica.</h1>
          <p style={{fontSize:16,color:'var(--vp-ink-2)',maxWidth:380,lineHeight:1.5,margin:0}}>
            Toni terra, legno e salvia. Tipografia umanista. Sensazione di <em>casa di famiglia</em>: morbida, accogliente, calma. Niente che ricordi un gestionale bancario.
          </p>
        </div>

        {/* Palette swatches */}
        <div>
          <div className="vp-eyebrow" style={{marginBottom:10}}>Palette</div>
          <div style={{display:'grid',gridTemplateColumns:'repeat(6,1fr)',gap:6}}>
            {[
              ['Terra',     'oklch(0.62 0.115 38)','#fff'],
              ['Salvia',    'oklch(0.58 0.055 145)','#fff'],
              ['Miele',     'oklch(0.72 0.105 75)','#3a2f24'],
              ['Argilla',   'oklch(0.55 0.110 25)','#fff'],
              ['Avena',     'oklch(0.94 0.018 75)','#3a2f24'],
              ['Inchiostro','oklch(0.26 0.022 50)','#fff'],
            ].map(([name,bg,fg]) => (
              <div key={name} style={{
                aspectRatio:'1',background:bg,borderRadius:10,
                padding:10,display:'flex',flexDirection:'column',justifyContent:'flex-end',
                color:fg,fontSize:11,fontWeight:500,
              }}>{name}</div>
            ))}
          </div>
        </div>

        {/* Type sample */}
        <div>
          <div className="vp-eyebrow" style={{marginBottom:10}}>Tipografia</div>
          <div style={{background:'var(--vp-cream)',padding:'18px 20px',borderRadius:14,border:'1px solid var(--vp-paper-3)'}}>
            <div style={{fontFamily:'var(--vp-font-display)',fontSize:38,letterSpacing:'-0.01em',lineHeight:1.05}}>
              Casa di Via Palestrina, ottobre.
            </div>
            <div style={{fontFamily:'var(--vp-font-display)',fontSize:14,color:'var(--vp-ink-3)',marginTop:6,fontStyle:'italic'}}>Source Serif 4 — display</div>
            <div style={{height:1,background:'var(--vp-paper-3)',margin:'14px 0'}}/>
            <div style={{fontFamily:'var(--vp-font-ui)',fontSize:15,lineHeight:1.5}}>
              Marco ha mandato una ricevuta di € 480,00 per l'affitto di ottobre. Vuoi confermare?
            </div>
            <div style={{fontFamily:'var(--vp-font-ui)',fontSize:12,color:'var(--vp-ink-3)',marginTop:6}}>Geist — UI</div>
          </div>
        </div>

        {/* Parole chiave */}
        <div style={{display:'flex',flexWrap:'wrap',gap:8}}>
          {['casa','legno','foglie','luce calda','manoscritto','ceramica','sabato mattina','quaderno'].map(w=>(
            <span key={w} style={{
              padding:'6px 14px',borderRadius:'var(--vp-r-pill)',
              background:'var(--vp-paper-2)',fontSize:13,color:'var(--vp-ink-2)',
              fontStyle:'italic',fontFamily:'var(--vp-font-display)',
            }}>{w}</span>
          ))}
        </div>
      </div>

      {/* moodboard collage */}
      <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gridTemplateRows:'1fr 1fr 0.6fr',gap:10}}>
        <div style={{
          gridRow:'span 2',
          background:'linear-gradient(160deg, oklch(0.92 0.045 40), oklch(0.78 0.085 40))',
          borderRadius:14,position:'relative',overflow:'hidden',
        }}>
          <div style={{position:'absolute',inset:0,background:'radial-gradient(circle at 30% 70%, oklch(0.96 0.04 70 / 0.4), transparent 60%)'}}/>
          <div style={{position:'absolute',bottom:14,left:14,color:'oklch(0.30 0.06 35)',fontSize:11,fontWeight:500}}>terracotta · pareti</div>
          <div style={{position:'absolute',top:'40%',left:'40%',transform:'translate(-50%,-50%) rotate(-12deg)',opacity:0.5}}>
            <VPRoof size={120} color="oklch(0.45 0.08 35)"/>
          </div>
        </div>
        <div style={{
          background:'oklch(0.55 0.05 145)',borderRadius:14,position:'relative',overflow:'hidden',
        }}>
          <div style={{position:'absolute',top:14,right:14}}><VPLeaf size={50} color="#fff"/></div>
          <div style={{position:'absolute',bottom:14,left:14,color:'#fff',fontSize:11,fontWeight:500,opacity:0.85}}>salvia · stati ok</div>
        </div>
        <div className="vp-paper-tex" style={{
          background:'var(--vp-paper-2)',borderRadius:14,padding:14,
          display:'flex',flexDirection:'column',justifyContent:'space-between',
        }}>
          <div style={{fontFamily:'var(--vp-font-display)',fontSize:18,lineHeight:1.2,fontStyle:'italic'}}>
            "L'ho aperta e in 10 secondi ho capito chi non aveva pagato."
          </div>
          <div style={{fontSize:11,color:'var(--vp-ink-3)'}}>— Laura, 3 fratelli</div>
        </div>
        <div style={{
          gridColumn:'span 2',background:'oklch(0.30 0.025 50)',borderRadius:14,
          padding:'14px 18px',color:'oklch(0.92 0.02 70)',
          display:'flex',alignItems:'center',gap:14,
        }}>
          <VPHouse size={48} color="oklch(0.85 0.06 40)" accent="oklch(0.78 0.08 145)"/>
          <div>
            <div style={{fontSize:13,opacity:0.7,marginBottom:2}}>tono</div>
            <div style={{fontFamily:'var(--vp-font-display)',fontSize:18,fontStyle:'italic'}}>
              "Manca ancora la ricevuta di Marco 🌿"
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function MoodBlock() {
  return (
    <div style={{
      width:'100%',height:'100%',padding:32,
      background:'oklch(0.985 0.004 90)',
      fontFamily:'var(--vp-font-ui)',color:'oklch(0.22 0.008 270)',
      display:'grid',gridTemplateColumns:'1.1fr 0.9fr',gap:24,
    }}>
      <div style={{display:'flex',flexDirection:'column',gap:18}}>
        <div>
          <div className="vp-eyebrow" style={{color:'oklch(0.55 0.130 28)'}}>Direzione 2 · Alternativa</div>
          <h1 style={{fontFamily:'"Geist",sans-serif',fontSize:54,margin:'4px 0 8px',lineHeight:0.95,letterSpacing:'-0.04em',fontWeight:500}}>Block organizer.</h1>
          <p style={{fontSize:16,color:'oklch(0.42 0.010 270)',maxWidth:380,lineHeight:1.5,margin:0}}>
            Stile Notion/Cron-like ma con accenti caldi. Più strutturato, più "attrezzo". Funzionale prima di tutto, calore solo nei dettagli (emoji, micro-illustrazioni, copy).
          </p>
        </div>
        <div>
          <div className="vp-eyebrow" style={{marginBottom:10}}>Palette</div>
          <div style={{display:'grid',gridTemplateColumns:'repeat(6,1fr)',gap:6}}>
            {[
              ['Mattone',  'oklch(0.60 0.140 30)','#fff'],
              ['Salvia',   'oklch(0.55 0.080 165)','#fff'],
              ['Senape',   'oklch(0.72 0.130 80)','#2a1f10'],
              ['Argilla',  'oklch(0.50 0.150 28)','#fff'],
              ['Carta',    'oklch(0.97 0.005 90)','#222'],
              ['Grafite',  'oklch(0.22 0.008 270)','#fff'],
            ].map(([name,bg,fg]) => (
              <div key={name} style={{
                aspectRatio:'1',background:bg,borderRadius:6,
                padding:10,display:'flex',flexDirection:'column',justifyContent:'flex-end',
                color:fg,fontSize:11,fontWeight:500,
              }}>{name}</div>
            ))}
          </div>
        </div>
        <div>
          <div className="vp-eyebrow" style={{marginBottom:10}}>Tipografia</div>
          <div style={{background:'#fff',padding:'18px 20px',borderRadius:8,border:'1px solid oklch(0.93 0.005 270)'}}>
            <div style={{fontFamily:'"Geist",sans-serif',fontSize:34,fontWeight:500,letterSpacing:'-0.03em',lineHeight:1.1}}>
              Via Palmieri / Ottobre 2026
            </div>
            <div style={{fontFamily:'"Geist",sans-serif',fontSize:13,color:'oklch(0.50 0.010 270)',marginTop:8}}>
              Inquilini · Pagamenti · Bollette · Conti
            </div>
          </div>
        </div>
        <div style={{
          padding:14,background:'#fff',borderRadius:8,
          border:'1px solid oklch(0.93 0.005 270)',
          fontSize:13,color:'oklch(0.42 0.010 270)',
        }}>
          <div style={{display:'flex',alignItems:'center',gap:8,marginBottom:6}}>
            <input type="checkbox" defaultChecked style={{accentColor:'oklch(0.60 0.140 30)'}}/>
            <span>Marco · affitto ottobre</span>
            <span style={{marginLeft:'auto',padding:'2px 8px',background:'oklch(0.93 0.040 165)',color:'oklch(0.40 0.080 165)',borderRadius:4,fontSize:11}}>pagato</span>
          </div>
          <div style={{display:'flex',alignItems:'center',gap:8,marginBottom:6}}>
            <input type="checkbox" style={{accentColor:'oklch(0.60 0.140 30)'}}/>
            <span>Yusuf · affitto ottobre</span>
            <span style={{marginLeft:'auto',padding:'2px 8px',background:'oklch(0.94 0.060 85)',color:'oklch(0.40 0.13 80)',borderRadius:4,fontSize:11}}>in attesa</span>
          </div>
          <div style={{fontSize:11,color:'oklch(0.55 0.010 270)',marginTop:6}}>list-block style — più data-density, meno "casa"</div>
        </div>
      </div>

      <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gridTemplateRows:'1fr 1fr',gap:10}}>
        {[
          ['oklch(0.96 0.018 30)',   'mattone tenue', 'oklch(0.45 0.130 28)'],
          ['oklch(0.97 0.025 80)',   'senape carta',  'oklch(0.42 0.13 80)'],
          ['oklch(0.96 0.020 165)',  'salvia chiara', 'oklch(0.40 0.080 165)'],
          ['oklch(0.97 0.005 90)',   'carta neutra',  'oklch(0.30 0.008 270)'],
        ].map(([bg,name,fg],i) => (
          <div key={i} style={{background:bg,borderRadius:8,padding:14,color:fg,fontSize:12,fontWeight:500,display:'flex',alignItems:'flex-end'}}>{name}</div>
        ))}
      </div>
    </div>
  );
}


// ────────────────────────────────────────────────────────
// Design System — palette, type, badge, table, card, banner
// ────────────────────────────────────────────────────────
function DesignSystem() {
  return (
    <div style={{width:'100%',height:'100%',padding:32,background:'var(--vp-paper)',fontFamily:'var(--vp-font-ui)',color:'var(--vp-ink)',overflow:'auto'}} className="vp-scroll">
      <div className="vp-eyebrow">Design system</div>
      <h1 className="vp-display" style={{fontSize:42,margin:'4px 0 30px'}}>Blocchi base</h1>

      <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:32}}>
        {/* Palette */}
        <Section title="Palette · semantica">
          <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:10}}>
            {[
              ['Terra · primario','var(--vp-terra)','azione, brand'],
              ['Salvia · ok','var(--vp-sage)','pagato, confermato'],
              ['Miele · attesa','var(--vp-honey)','in approvazione'],
              ['Argilla · ritardo','var(--vp-clay)','moroso, errore'],
              ['Avena · sfondo','var(--vp-paper-2)','superfici secondarie'],
              ['Inchiostro · testo','var(--vp-ink)','testo primario'],
            ].map(([name,bg,desc])=>(
              <div key={name} style={{display:'flex',alignItems:'center',gap:12}}>
                <div style={{width:48,height:48,background:bg,borderRadius:10,boxShadow:'var(--vp-shadow-1)',flexShrink:0}}/>
                <div>
                  <div style={{fontSize:13,fontWeight:500}}>{name}</div>
                  <div style={{fontSize:11,color:'var(--vp-ink-3)'}}>{desc}</div>
                </div>
              </div>
            ))}
          </div>
        </Section>

        {/* Type scale */}
        <Section title="Scala tipografica">
          <div style={{display:'flex',flexDirection:'column',gap:12,fontFamily:'var(--vp-font-display)'}}>
            <div style={{fontSize:44,lineHeight:1}}>Casa di Via Palestrina</div>
            <div style={{fontSize:30,lineHeight:1.05}}>Pagamenti · ottobre</div>
            <div style={{fontFamily:'var(--vp-font-ui)',fontSize:20,fontWeight:500}}>Sezione 20px Geist Medium</div>
            <div style={{fontFamily:'var(--vp-font-ui)',fontSize:15}}>Body 15px Geist Regular — leggibile a tutti.</div>
            <div style={{fontFamily:'var(--vp-font-ui)',fontSize:13,color:'var(--vp-ink-3)'}}>Caption 13px Geist · ink-3</div>
            <div className="vp-eyebrow">EYEBROW · 11PX UPPERCASE</div>
          </div>
        </Section>

        {/* Badge stati */}
        <Section title="Badge stato pagamento">
          <div style={{display:'flex',flexDirection:'column',gap:10,alignItems:'flex-start'}}>
            <span className="vp-badge vp-badge--ok"><span className="vp-dot vp-dot--ok"/>Ricevuto · 2 ott</span>
            <span className="vp-badge vp-badge--wait"><span className="vp-dot vp-dot--wait"/>Da approvare</span>
            <span className="vp-badge vp-badge--late"><span className="vp-dot vp-dot--late"/>In ritardo · 3g</span>
            <span className="vp-badge vp-badge--neutral">Bozza</span>
          </div>
          <div style={{fontSize:12,color:'var(--vp-ink-3)',marginTop:10}}>
            Pill morbide, mai rosse pure. Il "ritardo" è argilla, non rosso allarme.
          </div>
        </Section>

        {/* Banner */}
        <Section title="Banner sollecito">
          <div style={{display:'flex',flexDirection:'column',gap:8}}>
            <div className="vp-banner vp-banner--late">
              <VPIcon name="bell" size={16} color="var(--vp-clay)" style={{marginTop:2}}/>
              <div>Manca ancora la ricevuta di Marco 🌿</div>
            </div>
            <div className="vp-banner">
              <VPIcon name="alert" size={16} color="var(--vp-honey)" style={{marginTop:2}}/>
              <div>Bolletta gas in scadenza il 15 ottobre.</div>
            </div>
            <div className="vp-banner vp-banner--ok">
              <VPIcon name="check" size={16} color="var(--vp-sage-deep)" style={{marginTop:2}}/>
              <div>Tutti hanno pagato l'affitto di settembre. Bel mese.</div>
            </div>
          </div>
        </Section>

        {/* Card */}
        <Section title="Card pagamento">
          <div className="vp-card" style={{padding:18,maxWidth:340}}>
            <div style={{display:'flex',alignItems:'center',gap:12,marginBottom:14}}>
              <VPAvatar name="Sara" size={40} hue={50}/>
              <div style={{flex:1}}>
                <div style={{fontSize:15,fontWeight:500}}>Sara · Olmo</div>
                <div style={{fontSize:12,color:'var(--vp-ink-3)'}}>Ricevuto il 2 ottobre</div>
              </div>
              <span className="vp-badge vp-badge--ok"><span className="vp-dot vp-dot--ok"/>Pagato</span>
            </div>
            <div style={{display:'flex',justifyContent:'space-between',padding:'8px 0',borderTop:'1px solid var(--vp-paper-3)'}}>
              <span style={{fontSize:13,color:'var(--vp-ink-3)'}}>Affitto ottobre</span>
              <span className="vp-mono" style={{fontSize:14,fontWeight:500}}>€ 520,00</span>
            </div>
          </div>
        </Section>

        {/* Bottoni */}
        <Section title="Bottoni & input">
          <div style={{display:'flex',gap:8,marginBottom:14,flexWrap:'wrap'}}>
            <button className="vp-btn vp-btn--primary"><VPIcon name="check" size={14}/>Approva</button>
            <button className="vp-btn vp-btn--soft">Soft action</button>
            <button className="vp-btn vp-btn--ghost">Annulla</button>
          </div>
          <input className="vp-input" placeholder="Es. 480,00" style={{maxWidth:300}}/>
        </Section>

        {/* Tabella */}
        <Section title="Tabella semaforo" wide>
          <div className="vp-card" style={{overflow:'hidden'}}>
            <table className="vp-table">
              <thead>
                <tr><th>Inquilino</th><th>Affitto</th><th>Bollette</th><th>Stato</th></tr>
              </thead>
              <tbody>
                <tr><td><div style={{display:'flex',alignItems:'center',gap:10}}><VPAvatar name="Marco" size={26} hue={20}/>Marco</div></td><td className="vp-mono">€ 480</td><td className="vp-mono">€ 38</td><td><span className="vp-badge vp-badge--late"><span className="vp-dot vp-dot--late"/>Ritardo</span></td></tr>
                <tr><td><div style={{display:'flex',alignItems:'center',gap:10}}><VPAvatar name="Sara" size={26} hue={50}/>Sara</div></td><td className="vp-mono">€ 520</td><td className="vp-mono">€ 42</td><td><span className="vp-badge vp-badge--ok"><span className="vp-dot vp-dot--ok"/>Pagato</span></td></tr>
                <tr><td><div style={{display:'flex',alignItems:'center',gap:10}}><VPAvatar name="Yusuf" size={26} hue={120}/>Yusuf</div></td><td className="vp-mono">€ 540</td><td className="vp-mono">€ 45</td><td><span className="vp-badge vp-badge--wait"><span className="vp-dot vp-dot--wait"/>Da approvare</span></td></tr>
              </tbody>
            </table>
          </div>
        </Section>
      </div>
    </div>
  );
}

function Section({ title, children, wide }) {
  return (
    <div style={{gridColumn:wide?'span 2':'auto'}}>
      <div style={{fontSize:12,fontWeight:500,letterSpacing:'0.06em',textTransform:'uppercase',color:'var(--vp-ink-3)',marginBottom:14,paddingBottom:10,borderBottom:'1px solid var(--vp-paper-3)'}}>{title}</div>
      {children}
    </div>
  );
}


// ────────────────────────────────────────────────────────
// Sitemap visiva
// ────────────────────────────────────────────────────────
function Sitemap() {
  const desktop = [
    'Dashboard rendita','Inquilini & contratti','Pagamenti affitto',
    'Bollette & conguagli','Spese generali','Manutenzioni',
    'Conti tra fratelli','Documenti','Reportistica','Configurazione',
  ];
  const mobileTen = [
    'Home / Saldo','Pagamenti','Invia ricevuta','Dettaglio bolletta',
    'Segnala guasto','Documenti','Profilo','Notifiche & messaggi',
  ];
  const mobileOwner = [
    'Home rapida','Approva ricevuta','Quick-add spesa',
    'Stato pagamenti','Sollecita','Ticket manutenzioni',
  ];

  return (
    <div style={{width:'100%',height:'100%',padding:32,background:'var(--vp-paper)',color:'var(--vp-ink)',fontFamily:'var(--vp-font-ui)',overflow:'auto'}} className="vp-scroll">
      <div className="vp-eyebrow">Architettura informativa</div>
      <h1 className="vp-display" style={{fontSize:40,margin:'4px 0 6px'}}>Sitemap visiva</h1>
      <p style={{color:'var(--vp-ink-2)',fontSize:15,maxWidth:680,margin:'0 0 28px'}}>
        Tre superfici, un'unica casa. Desktop per i fratelli che gestiscono. Mobile per inquilini (poche cose, semplici) e per i fratelli quando sono in giro.
      </p>

      <div style={{display:'grid',gridTemplateColumns:'1.4fr 1fr 1fr',gap:18}}>
        {/* Desktop */}
        <SitemapColumn
          icon={<VPIcon name="chart" size={18}/>}
          tag="Desktop"
          title="Area proprietari"
          subtitle="Back-office, riconciliazione, decisioni"
          items={desktop}
          accent="var(--vp-terra)"
          badges={['Dashboard rendita','Bollette & conguagli','Conti tra fratelli']}
        />
        <SitemapColumn
          icon={<VPIcon name="user" size={18}/>}
          tag="Mobile"
          title="Area inquilino"
          subtitle="Poche azioni, sempre a portata"
          items={mobileTen}
          accent="var(--vp-sage)"
          badges={['Invia ricevuta']}
        />
        <SitemapColumn
          icon={<VPIcon name="users" size={18}/>}
          tag="Mobile"
          title="Proprietario, in giro"
          subtitle="Approvare e rispondere veloce"
          items={mobileOwner}
          accent="var(--vp-honey)"
          badges={['Approva ricevuta']}
        />
      </div>

      <div style={{marginTop:32,padding:'18px 22px',borderRadius:14,background:'var(--vp-paper-2)',display:'flex',alignItems:'center',gap:14}}>
        <VPLeaf size={28}/>
        <div style={{fontSize:14,color:'var(--vp-ink-2)'}}>
          I <span style={{padding:'2px 8px',borderRadius:6,background:'var(--vp-terra-soft)',color:'var(--vp-terra-deep)',fontSize:12,fontWeight:500}}>flussi chiave</span>{' '}
          (in evidenza nelle colonne) sono i 5 prototipi cliccabili qui sotto. Tutto il resto è strutturato ma non ancora disegnato in alta fedeltà.
        </div>
      </div>
    </div>
  );
}

function SitemapColumn({ icon, tag, title, subtitle, items, accent, badges }) {
  return (
    <div className="vp-card" style={{padding:'22px 22px',display:'flex',flexDirection:'column',gap:10}}>
      <div style={{display:'flex',alignItems:'center',gap:10,marginBottom:4}}>
        <div style={{width:32,height:32,borderRadius:8,background:accent,color:'#fff',display:'flex',alignItems:'center',justifyContent:'center'}}>
          {icon}
        </div>
        <div>
          <div className="vp-eyebrow" style={{color:accent}}>{tag}</div>
          <div className="vp-display" style={{fontSize:18}}>{title}</div>
        </div>
      </div>
      <div style={{fontSize:13,color:'var(--vp-ink-3)',marginBottom:10}}>{subtitle}</div>
      <div style={{display:'flex',flexDirection:'column',gap:6}}>
        {items.map((it,i)=>{
          const isKey = badges.includes(it);
          return (
            <div key={i} style={{
              display:'flex',alignItems:'center',gap:10,
              padding:'9px 12px',borderRadius:8,
              background: isKey ? 'var(--vp-terra-soft)' : 'var(--vp-paper-2)',
              fontSize:13,fontWeight:isKey?500:400,
              color: isKey ? 'var(--vp-terra-deep)' : 'var(--vp-ink-2)',
            }}>
              <span style={{
                width:18,fontSize:11,color:isKey?'var(--vp-terra-deep)':'var(--vp-ink-4)',
                fontFamily:'var(--vp-font-mono)',
              }}>{(i+1).toString().padStart(2,'0')}</span>
              <span style={{flex:1}}>{it}</span>
              {isKey && <span style={{fontSize:10,padding:'2px 6px',borderRadius:4,background:'var(--vp-terra)',color:'#fff',fontWeight:500}}>FLUSSO</span>}
            </div>
          );
        })}
      </div>
    </div>
  );
}


// ────────────────────────────────────────────────────────
// Stati vuoti & errori — 3 scelti
// ────────────────────────────────────────────────────────
function EmptyDashboard() {
  return (
    <div style={{width:'100%',height:'100%',background:'var(--vp-paper)',color:'var(--vp-ink)',fontFamily:'var(--vp-font-ui)',padding:'48px 36px',display:'flex',flexDirection:'column'}}>
      <div className="vp-eyebrow">Dashboard rendita · primo accesso</div>
      <h1 className="vp-display" style={{fontSize:30,margin:'4px 0 24px'}}>Casa nuova, niente da vedere ancora.</h1>
      <div style={{display:'flex',alignItems:'center',justifyContent:'center',flex:1,padding:28}}>
        <div style={{textAlign:'center',maxWidth:380,display:'flex',flexDirection:'column',alignItems:'center',gap:18}}>
          <div style={{position:'relative'}}>
            <VPHouse size={120}/>
            <div style={{position:'absolute',bottom:-6,left:-12,opacity:0.7}}><VPLeaf size={40}/></div>
          </div>
          <div className="vp-display" style={{fontSize:26,marginBottom:-6}}>Iniziamo dai vostri inquilini.</div>
          <p style={{color:'var(--vp-ink-2)',fontSize:15,lineHeight:1.5,margin:0}}>
            Aggiungete chi vive in casa con voi: appena uno di loro carica una ricevuta, qui troverete tutto.
          </p>
          <div style={{display:'flex',gap:10}}>
            <button className="vp-btn vp-btn--primary"><VPIcon name="plus" size={16}/>Aggiungi inquilino</button>
            <button className="vp-btn vp-btn--ghost">Importa da contratto</button>
          </div>
        </div>
      </div>
    </div>
  );
}

function ErrorReceipt() {
  return (
    <div style={{width:'100%',height:'100%',background:'var(--vp-paper)',color:'var(--vp-ink)',fontFamily:'var(--vp-font-ui)',padding:'40px 28px',display:'flex',flexDirection:'column',alignItems:'center',textAlign:'center',gap:18}}>
      <div className="vp-eyebrow" style={{alignSelf:'flex-start'}}>Inquilino · errore caricamento</div>
      <div style={{flex:1,display:'flex',flexDirection:'column',alignItems:'center',justifyContent:'center',gap:18,maxWidth:300}}>
        <div style={{
          width:120,aspectRatio:'0.7',background:'#f4ede1',borderRadius:8,
          padding:'8px 8px',transform:'rotate(-6deg)',position:'relative',
          fontFamily:'var(--vp-font-mono)',fontSize:7,color:'#3a2f24',
          boxShadow:'var(--vp-shadow-2)',
        }}>
          <div style={{textAlign:'center',fontWeight:700}}>BONIFICO</div>
          <div style={{borderBottom:'1px dashed #b8a784',margin:'3px 0'}}/>
          <div style={{filter:'blur(2.5px)'}}>Da: ███████</div>
          <div style={{filter:'blur(2.5px)'}}>Causale: ████ ████</div>
          <div style={{position:'absolute',inset:0,display:'flex',alignItems:'center',justifyContent:'center'}}>
            <div style={{background:'var(--vp-clay-soft)',borderRadius:'50%',width:36,height:36,display:'flex',alignItems:'center',justifyContent:'center'}}>
              <VPIcon name="alert" size={20} color="var(--vp-clay)"/>
            </div>
          </div>
        </div>
        <div className="vp-display" style={{fontSize:24}}>La foto non è leggibile.</div>
        <p style={{color:'var(--vp-ink-2)',fontSize:14,lineHeight:1.5,margin:0}}>
          Non riusciamo a riconoscere causale e importo. Riprova in piena luce, oppure scrivi tu i dati a mano — ci pensiamo dopo.
        </p>
        <div style={{display:'flex',gap:10,flexDirection:'column',width:'100%'}}>
          <button className="vp-btn vp-btn--primary" style={{width:'100%'}}><VPIcon name="camera" size={16}/>Riprova foto</button>
          <button className="vp-btn vp-btn--ghost" style={{width:'100%'}}>Inserisci a mano</button>
        </div>
      </div>
    </div>
  );
}

function EmptyTickets() {
  return (
    <div style={{width:'100%',height:'100%',background:'var(--vp-paper)',color:'var(--vp-ink)',fontFamily:'var(--vp-font-ui)',padding:'48px 36px',display:'flex',flexDirection:'column'}}>
      <div className="vp-eyebrow">Manutenzioni · stato vuoto</div>
      <h1 className="vp-display" style={{fontSize:30,margin:'4px 0 24px'}}>Tutto in ordine.</h1>
      <div style={{display:'flex',alignItems:'center',justifyContent:'center',flex:1}}>
        <div style={{textAlign:'center',maxWidth:380,display:'flex',flexDirection:'column',alignItems:'center',gap:14}}>
          <div style={{
            width:120,height:120,borderRadius:'50%',
            background:'var(--vp-sage-soft)',display:'flex',alignItems:'center',justifyContent:'center',
            position:'relative',
          }}>
            <VPIcon name="wrench" size={48} color="var(--vp-sage-deep)" stroke={1.6}/>
            <div style={{position:'absolute',top:-8,right:-4,fontSize:30}}>🌿</div>
          </div>
          <div className="vp-display" style={{fontSize:26}}>Nessun guasto aperto.</div>
          <p style={{color:'var(--vp-ink-2)',fontSize:15,lineHeight:1.5,margin:0}}>
            La casa sta bene. L'ultimo intervento è stato il <b>12 settembre</b> — l'idraulico per il rubinetto della cucina.
          </p>
          <button className="vp-btn vp-btn--ghost" style={{marginTop:6}}><VPIcon name="clock" size={14}/>Vedi storico</button>
        </div>
      </div>
    </div>
  );
}


// ────────────────────────────────────────────────────────
// Icona PWA + splash (3 opzioni)
// ────────────────────────────────────────────────────────
function IconOption({ option }) {
  const opts = {
    A: {
      title: 'Tetto + foglia',
      sub: 'Il segno più riconoscibile: casa che cresce.',
      bg: 'oklch(0.62 0.115 38)',
      content: (
        <svg viewBox="0 0 100 100" width="80%" height="80%">
          <path d="M18 58 L50 22 L82 58" stroke="#fff" strokeWidth="6" fill="none" strokeLinecap="round" strokeLinejoin="round"/>
          <path d="M30 70 C30 50, 45 38, 68 38 C62 60, 50 70, 30 70 Z" fill="oklch(0.78 0.085 145)" opacity="0.95"/>
          <path d="M30 70 L58 44" stroke="oklch(0.45 0.08 145)" strokeWidth="2" opacity="0.5"/>
        </svg>
      ),
    },
    B: {
      title: 'Monogramma V',
      sub: 'Tipografica, sobria. Funziona piccolissima.',
      bg: 'oklch(0.94 0.018 75)',
      fg: 'var(--vp-ink)',
      content: (
        <div style={{
          fontFamily:'var(--vp-font-display)',fontSize:80,fontWeight:500,
          color:'var(--vp-terra)',lineHeight:1,letterSpacing:'-0.03em',
          display:'flex',alignItems:'flex-end',
        }}>
          V<span style={{fontSize:30,color:'var(--vp-leaf)',marginBottom:14,marginLeft:-4}}>·</span>
        </div>
      ),
    },
    C: {
      title: 'Casa minima',
      sub: 'Pittogramma puro. Più "app store-friendly".',
      bg: 'oklch(0.55 0.05 145)',
      content: (
        <svg viewBox="0 0 100 100" width="80%" height="80%">
          <rect x="20" y="42" width="60" height="48" rx="4" fill="none" stroke="#fff" strokeWidth="6"/>
          <path d="M14 48 L50 18 L86 48" stroke="#fff" strokeWidth="6" fill="none" strokeLinecap="round" strokeLinejoin="round"/>
          <rect x="42" y="62" width="16" height="28" fill="#fff"/>
          <circle cx="50" cy="76" r="1.5" fill={"oklch(0.50 0.06 145)"}/>
        </svg>
      ),
    },
  };
  const o = opts[option];
  return (
    <div style={{display:'flex',flexDirection:'column',alignItems:'center',gap:14}}>
      <div style={{
        width:160,height:160,background:o.bg,borderRadius:36,
        display:'flex',alignItems:'center',justifyContent:'center',
        boxShadow:'var(--vp-shadow-3)',
      }}>{o.content}</div>
      {/* size variants */}
      <div style={{display:'flex',gap:10,alignItems:'flex-end'}}>
        {[64,40,24].map(s=>(
          <div key={s} style={{
            width:s,height:s,background:o.bg,borderRadius:s*0.22,
            display:'flex',alignItems:'center',justifyContent:'center',
            transform:'scale(1)',
          }}>
            <div style={{width:'80%',height:'80%',display:'flex',alignItems:'center',justifyContent:'center',transform:`scale(${s/80})`,transformOrigin:'center'}}>
              {o.content}
            </div>
          </div>
        ))}
      </div>
      <div style={{textAlign:'center'}}>
        <div className="vp-display" style={{fontSize:18}}>Opzione {option} — {o.title}</div>
        <div style={{fontSize:12,color:'var(--vp-ink-3)',maxWidth:200,marginTop:4}}>{o.sub}</div>
      </div>
    </div>
  );
}

function IconExploration() {
  return (
    <div style={{width:'100%',height:'100%',padding:32,background:'var(--vp-paper)',color:'var(--vp-ink)',fontFamily:'var(--vp-font-ui)',overflow:'auto'}} className="vp-scroll">
      <div className="vp-eyebrow">Identità · icona PWA</div>
      <h1 className="vp-display" style={{fontSize:36,margin:'4px 0 6px'}}>Tre direzioni per l'icona</h1>
      <p style={{color:'var(--vp-ink-2)',fontSize:14,maxWidth:600,margin:'0 0 30px'}}>
        Tutte testate da 24px (notifica) a 160px (splash). Sceglie la sorella di Giulio — non un brand designer.
      </p>
      <div style={{display:'grid',gridTemplateColumns:'1fr 1fr 1fr',gap:24,marginBottom:36}}>
        <IconOption option="A"/>
        <IconOption option="B"/>
        <IconOption option="C"/>
      </div>

      {/* Splash */}
      <div className="vp-eyebrow" style={{marginBottom:14}}>Splash screen — opzione A</div>
      <div style={{
        width:280,height:560,borderRadius:32,overflow:'hidden',
        background:'oklch(0.62 0.115 38)',
        display:'flex',flexDirection:'column',alignItems:'center',justifyContent:'center',gap:18,
        margin:'0 auto',position:'relative',
        boxShadow:'var(--vp-shadow-3)',
      }}>
        <div style={{position:'absolute',inset:0,opacity:0.15}}>
          <div style={{position:'absolute',top:'15%',left:'20%'}}><VPLeaf size={60} color="#fff"/></div>
          <div style={{position:'absolute',bottom:'18%',right:'18%'}}><VPLeaf size={40} color="#fff"/></div>
        </div>
        <svg viewBox="0 0 100 100" width="120" height="120" style={{zIndex:1}}>
          <path d="M18 58 L50 22 L82 58" stroke="#fff" strokeWidth="6" fill="none" strokeLinecap="round" strokeLinejoin="round"/>
          <path d="M30 70 C30 50, 45 38, 68 38 C62 60, 50 70, 30 70 Z" fill="oklch(0.92 0.06 145)" opacity="0.95"/>
        </svg>
        <div style={{fontFamily:'var(--vp-font-display)',fontSize:42,color:'#fff',letterSpacing:'-0.02em'}}>Viapal</div>
        <div style={{fontSize:13,color:'rgba(255,255,255,0.75)',fontStyle:'italic',fontFamily:'var(--vp-font-display)'}}>la casa, in tasca</div>
      </div>
    </div>
  );
}


Object.assign(window, {
  MoodMaterica, MoodBlock, DesignSystem, Sitemap,
  EmptyDashboard, ErrorReceipt, EmptyTickets, IconExploration,
});
