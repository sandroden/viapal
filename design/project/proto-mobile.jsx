/* global React, VPIcon, VPLeaf, VPEnvelope, VPHouse, VPAvatar, IOSDevice, IOSStatusBar */

// ── Prototipo 2: Inquilino invia ricevuta (mobile) ─────────────
function ProtoInviaRicevuta() {
  const [step, setStep] = React.useState(0); // 0 home, 1 scatta, 2 dettagli, 3 conferma
  const [causale, setCausale] = React.useState('affitto');
  const [importo, setImporto] = React.useState('480');

  return (
    <div style={{
      width:'100%', height:'100%', background:'var(--vp-paper)',
      color:'var(--vp-ink)', fontFamily:'var(--vp-font-ui)',
      display:'flex', flexDirection:'column', position:'relative', overflow:'hidden',
    }}>
      <IOSStatusBar/>
      {step === 0 && <RentHome onNew={()=>setStep(1)}/>}
      {step === 1 && <RentCapture onNext={()=>setStep(2)} onBack={()=>setStep(0)}/>}
      {step === 2 && <RentDetails causale={causale} setCausale={setCausale} importo={importo} setImporto={setImporto} onNext={()=>setStep(3)} onBack={()=>setStep(1)}/>}
      {step === 3 && <RentConfirm importo={importo} causale={causale} onDone={()=>setStep(0)}/>}
    </div>
  );
}

function RentHome({ onNew }) {
  return (
    <div style={{flex:1,overflow:'auto',padding:'8px 20px 28px'}} className="vp-scroll">
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:18}}>
        <div>
          <div style={{fontSize:13,color:'var(--vp-ink-3)'}}>Ciao,</div>
          <div className="vp-display" style={{fontSize:24}}>Marco</div>
        </div>
        <div style={{position:'relative'}}>
          <div style={{width:42,height:42,borderRadius:'50%',background:'var(--vp-paper-2)',display:'flex',alignItems:'center',justifyContent:'center'}}>
            <VPIcon name="bell" size={20}/>
          </div>
          <div style={{position:'absolute',top:6,right:6,width:8,height:8,borderRadius:'50%',background:'var(--vp-clay)'}}/>
        </div>
      </div>

      {/* Saldo */}
      <div style={{
        position:'relative',overflow:'hidden',
        background:'var(--vp-cream)',border:'1px solid var(--vp-paper-3)',
        borderRadius:'var(--vp-r-xl)',padding:'22px 22px 24px',
        boxShadow:'var(--vp-shadow-2)',
      }}>
        <div className="vp-eyebrow">Da pagare ora</div>
        <div className="vp-display" style={{fontSize:44,marginTop:6,letterSpacing:'-0.02em'}}>€ 480,00</div>
        <div style={{fontSize:13,color:'var(--vp-ink-2)',marginTop:4}}>Affitto ottobre · scaduto da 3 giorni</div>
        <div style={{position:'absolute',right:-14,top:-10,opacity:0.10}}><VPHouse size={120}/></div>
        <button onClick={onNew} className="vp-btn vp-btn--primary" style={{width:'100%',height:48,marginTop:16,fontSize:15}}>
          <VPIcon name="camera" size={18}/> Invia ricevuta
        </button>
      </div>

      <div className="vp-eyebrow" style={{marginTop:26,marginBottom:10}}>Storico recente</div>
      {[
        {label:'Bolletta luce · sett',date:'28 set',amount:'€ 38,50',ok:true},
        {label:'Affitto · settembre',date:'1 set',amount:'€ 480,00',ok:true},
        {label:'Conguaglio gas estate',date:'12 ago',amount:'€ 62,00',ok:true},
      ].map((r,i)=>(
        <div key={i} style={{
          display:'flex',alignItems:'center',gap:12,padding:'14px 4px',
          borderBottom:'1px solid var(--vp-paper-3)',
        }}>
          <div style={{width:36,height:36,borderRadius:10,background:'var(--vp-sage-soft)',display:'flex',alignItems:'center',justifyContent:'center',color:'var(--vp-sage-deep)'}}>
            <VPIcon name="check" size={18}/>
          </div>
          <div style={{flex:1}}>
            <div style={{fontSize:14,fontWeight:500}}>{r.label}</div>
            <div style={{fontSize:12,color:'var(--vp-ink-3)'}}>{r.date}</div>
          </div>
          <div className="vp-mono" style={{fontSize:14}}>{r.amount}</div>
        </div>
      ))}

      <div className="vp-eyebrow" style={{marginTop:26,marginBottom:10}}>Casa</div>
      <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:10}}>
        {[
          ['wrench','Segnala guasto'],
          ['folder','Documenti'],
          ['contract','Il mio contratto'],
          ['message','Scrivi ai proprietari'],
        ].map(([icon,label],i)=>(
          <div key={i} className="vp-card" style={{padding:14,display:'flex',alignItems:'center',gap:10}}>
            <VPIcon name={icon} size={18} color="var(--vp-terra)"/>
            <span style={{fontSize:13}}>{label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function RentCapture({ onNext, onBack }) {
  return (
    <div style={{flex:1,display:'flex',flexDirection:'column',background:'oklch(0.18 0.01 50)',color:'#fff'}}>
      <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',padding:'12px 20px'}}>
        <button onClick={onBack} style={{background:'transparent',border:'none',color:'#fff',padding:8,cursor:'pointer'}}>
          <VPIcon name="x" size={22} color="#fff"/>
        </button>
        <div style={{fontSize:15,fontWeight:500}}>Scatta la ricevuta</div>
        <button style={{background:'transparent',border:'none',color:'#fff',padding:8,fontSize:14}}>Carica</button>
      </div>
      <div style={{flex:1,position:'relative',display:'flex',alignItems:'center',justifyContent:'center'}}>
        {/* Finestra di mira con scontrino simulato */}
        <div style={{
          position:'absolute',inset:'14% 12%',border:'2px dashed rgba(255,255,255,0.5)',
          borderRadius:16,
        }}/>
        <div style={{
          width:'66%',aspectRatio:'0.62',background:'#f4ede1',borderRadius:6,
          padding:'14px 12px',transform:'rotate(-2deg)',
          boxShadow:'0 30px 60px rgba(0,0,0,0.5)',
          fontFamily:'var(--vp-font-mono)',fontSize:9,color:'#3a2f24',
          display:'flex',flexDirection:'column',gap:4,
        }}>
          <div style={{textAlign:'center',fontSize:10,fontWeight:600,letterSpacing:1}}>BANCA INTESA · BONIFICO</div>
          <div style={{borderBottom:'1px dashed #b8a784',margin:'6px 0'}}/>
          <div>Da: M. ROSSI</div>
          <div>A: ELENA + GIULIO + L. BIANCHI</div>
          <div>IBAN: IT60 X054 2811 1010 0000</div>
          <div>Causale: Affitto ottobre 2026</div>
          <div style={{borderBottom:'1px dashed #b8a784',margin:'6px 0'}}/>
          <div style={{fontSize:14,fontWeight:600,textAlign:'right'}}>EUR 480,00</div>
          <div style={{fontSize:8,color:'#7a6852'}}>04/10/2026 · 14:32 · TRN 8826491</div>
        </div>
        <div style={{position:'absolute',bottom:24,left:0,right:0,textAlign:'center',fontSize:13,color:'rgba(255,255,255,0.8)'}}>
          Centra il documento nel riquadro
        </div>
      </div>
      <div style={{padding:'18px 24px 28px',display:'flex',justifyContent:'center',alignItems:'center',gap:36}}>
        <div style={{width:48,height:48,borderRadius:10,background:'rgba(255,255,255,0.15)',display:'flex',alignItems:'center',justifyContent:'center'}}>
          <VPIcon name="folder" size={20} color="#fff"/>
        </div>
        <button onClick={onNext} style={{
          width:74,height:74,borderRadius:'50%',
          background:'#fff',border:'4px solid rgba(255,255,255,0.4)',
          cursor:'pointer',
        }}/>
        <div style={{width:48,height:48}}/>
      </div>
    </div>
  );
}

function RentDetails({ causale, setCausale, importo, setImporto, onNext, onBack }) {
  return (
    <div style={{flex:1,display:'flex',flexDirection:'column',overflow:'auto'}} className="vp-scroll">
      <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',padding:'10px 16px'}}>
        <button onClick={onBack} style={{background:'transparent',border:'none',padding:8,cursor:'pointer'}}>
          <VPIcon name="back" size={22}/>
        </button>
        <div style={{fontSize:15,fontWeight:500}}>Dettagli</div>
        <div style={{width:38}}/>
      </div>
      <div style={{padding:'12px 20px 28px',display:'flex',flexDirection:'column',gap:18}}>
        {/* preview */}
        <div style={{
          alignSelf:'center',width:170,aspectRatio:'0.7',background:'#f4ede1',
          borderRadius:8,padding:'12px 10px',transform:'rotate(-1.5deg)',
          boxShadow:'var(--vp-shadow-3)',
          fontFamily:'var(--vp-font-mono)',fontSize:7,color:'#3a2f24',
          display:'flex',flexDirection:'column',gap:3,
        }}>
          <div style={{textAlign:'center',fontWeight:700,fontSize:8}}>BONIFICO · INTESA</div>
          <div style={{borderBottom:'1px dashed #b8a784',margin:'3px 0'}}/>
          <div>Causale: Affitto ott 2026</div>
          <div>Da: M. Rossi</div>
          <div style={{borderBottom:'1px dashed #b8a784',margin:'3px 0'}}/>
          <div style={{textAlign:'right',fontWeight:700,fontSize:11}}>€ 480,00</div>
          <div style={{position:'absolute'}}/>
        </div>

        <div className="vp-banner vp-banner--ok" style={{fontSize:13}}>
          <VPIcon name="check" size={16} color="var(--vp-sage-deep)" style={{marginTop:2}}/>
          <div><b>Riconosciuto:</b> sembra il bonifico per l'<b>affitto di ottobre</b> di € 480.</div>
        </div>

        <div>
          <label className="vp-eyebrow" style={{display:'block',marginBottom:8}}>Causale</label>
          <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:8}}>
            {[
              ['affitto','Affitto','home'],
              ['bolletta','Bolletta','bills'],
              ['conguaglio','Conguaglio','euro'],
              ['cauzione','Cauzione','key'],
            ].map(([k,l,ic]) => (
              <button key={k} onClick={()=>setCausale(k)} style={{
                display:'flex',alignItems:'center',gap:8,
                padding:'12px 14px',borderRadius:12,cursor:'pointer',
                background: causale===k?'var(--vp-terra-soft)':'var(--vp-paper-2)',
                border:`1.5px solid ${causale===k?'var(--vp-terra)':'transparent'}`,
                color: causale===k?'var(--vp-terra-deep)':'var(--vp-ink)',
                fontSize:14,fontWeight:causale===k?500:400,
                fontFamily:'inherit',
              }}>
                <VPIcon name={ic} size={16}/>{l}
              </button>
            ))}
          </div>
        </div>

        <div>
          <label className="vp-eyebrow" style={{display:'block',marginBottom:8}}>Importo</label>
          <div style={{
            display:'flex',alignItems:'center',background:'var(--vp-cream)',
            border:'1px solid var(--vp-paper-3)',borderRadius:12,padding:'4px 14px',
          }}>
            <span style={{fontFamily:'var(--vp-font-display)',fontSize:24,color:'var(--vp-ink-3)',marginRight:6}}>€</span>
            <input value={importo} onChange={e=>setImporto(e.target.value)} style={{
              flex:1,border:'none',outline:'none',background:'transparent',
              fontFamily:'var(--vp-font-display)',fontSize:28,padding:'8px 0',
              color:'var(--vp-ink)',
            }}/>
          </div>
        </div>

        <div>
          <label className="vp-eyebrow" style={{display:'block',marginBottom:8}}>Mese di riferimento</label>
          <div style={{display:'flex',gap:8,overflowX:'auto'}} className="vp-scroll">
            {['Ago','Set','Ott','Nov','Dic'].map((m,i)=>(
              <div key={m} style={{
                padding:'10px 16px',borderRadius:'var(--vp-r-pill)',
                background:i===2?'var(--vp-ink)':'var(--vp-paper-2)',
                color:i===2?'var(--vp-cream)':'var(--vp-ink-2)',
                fontSize:13,fontWeight:500,whiteSpace:'nowrap',
              }}>{m} 2026</div>
            ))}
          </div>
        </div>

        <textarea placeholder="Note (facoltativo)" rows={2} style={{
          width:'100%',padding:14,border:'1px solid var(--vp-paper-3)',
          borderRadius:12,background:'var(--vp-cream)',resize:'none',
          fontFamily:'inherit',fontSize:14,outline:'none',
        }}/>
      </div>
      <div style={{padding:'14px 20px 24px',background:'var(--vp-paper)',borderTop:'1px solid var(--vp-paper-3)'}}>
        <button onClick={onNext} className="vp-btn vp-btn--primary" style={{width:'100%',height:48,fontSize:15}}>
          Invia a Elena, Giulio e Laura
        </button>
      </div>
    </div>
  );
}

function RentConfirm({ importo, onDone }) {
  return (
    <div style={{flex:1,display:'flex',flexDirection:'column',alignItems:'center',justifyContent:'center',padding:'30px 28px',textAlign:'center',gap:18}}>
      <div style={{width:96,height:96,borderRadius:'50%',background:'var(--vp-sage-soft)',display:'flex',alignItems:'center',justifyContent:'center',marginBottom:8}}>
        <VPIcon name="check" size={44} color="var(--vp-sage-deep)" stroke={2.4}/>
      </div>
      <div className="vp-display" style={{fontSize:30}}>Fatto, Marco.</div>
      <div style={{color:'var(--vp-ink-2)',fontSize:15,lineHeight:1.5,maxWidth:280}}>
        Abbiamo avvisato i proprietari del bonifico di <b>€ {importo}</b>. Ti scriveremo qui appena confermato.
      </div>
      <div style={{
        background:'var(--vp-paper-2)',padding:'14px 18px',borderRadius:12,
        display:'flex',alignItems:'center',gap:12,fontSize:13,color:'var(--vp-ink-2)',
      }}>
        <VPLeaf size={28}/>
        <span>Di solito Elena risponde entro mezza giornata.</span>
      </div>
      <button onClick={onDone} className="vp-btn vp-btn--ghost" style={{marginTop:'auto'}}>
        Torna alla home
      </button>
    </div>
  );
}

window.ProtoInviaRicevuta = ProtoInviaRicevuta;


// ── Prototipo 3: Proprietario approva ricevuta (mobile) ──────
function ProtoApprovaRicevuta() {
  const [step, setStep] = React.useState(0); // 0 notifica, 1 dettaglio, 2 conferma
  return (
    <div style={{
      width:'100%',height:'100%',position:'relative',overflow:'hidden',
      background: step===0 ? 'oklch(0.20 0.012 50)' : 'var(--vp-paper)',
      color:'var(--vp-ink)',fontFamily:'var(--vp-font-ui)',
    }}>
      <IOSStatusBar dark={step===0}/>
      {step === 0 && <ApproveLockNotif onTap={()=>setStep(1)}/>}
      {step === 1 && <ApproveDetail onConfirm={()=>setStep(2)} onBack={()=>setStep(0)}/>}
      {step === 2 && <ApproveDone onDone={()=>setStep(0)}/>}
    </div>
  );
}

function ApproveLockNotif({ onTap }) {
  return (
    <div style={{flex:1,height:'calc(100% - 54px)',display:'flex',flexDirection:'column',color:'#fff',padding:'18px 20px',
      backgroundImage:'radial-gradient(ellipse at 30% 20%, oklch(0.32 0.04 40 / 0.6), transparent 60%), radial-gradient(ellipse at 80% 80%, oklch(0.30 0.05 145 / 0.4), transparent 60%)',
    }}>
      <div style={{textAlign:'center',marginTop:30,fontSize:78,fontWeight:200,letterSpacing:'-0.04em'}}>14:32</div>
      <div style={{textAlign:'center',fontSize:15,opacity:0.85,marginTop:-4}}>giovedì 4 ottobre</div>
      <div style={{flex:1}}/>
      <div onClick={onTap} style={{
        background:'rgba(40,30,22,0.5)',backdropFilter:'blur(20px)',
        WebkitBackdropFilter:'blur(20px)',
        borderRadius:18,padding:'14px 16px',marginBottom:30,cursor:'pointer',
        border:'1px solid rgba(255,255,255,0.08)',
      }}>
        <div style={{display:'flex',alignItems:'center',gap:10,marginBottom:8}}>
          <div style={{width:24,height:24,borderRadius:6,background:'var(--vp-terra)',display:'flex',alignItems:'center',justifyContent:'center',fontFamily:'var(--vp-font-display)',fontSize:13,color:'#fff'}}>V</div>
          <div style={{fontSize:13,fontWeight:500,flex:1}}>Viapal</div>
          <div style={{fontSize:12,opacity:0.7}}>adesso</div>
        </div>
        <div style={{fontSize:15,fontWeight:600,marginBottom:2}}>Marco ha mandato una ricevuta 🌿</div>
        <div style={{fontSize:14,opacity:0.85,lineHeight:1.4}}>Affitto ottobre · € 480,00 — tocca per confermare</div>
      </div>
    </div>
  );
}

function ApproveDetail({ onConfirm, onBack }) {
  const [importo, setImporto] = React.useState('480');
  return (
    <div style={{flex:1,height:'calc(100% - 54px)',display:'flex',flexDirection:'column',overflow:'auto'}} className="vp-scroll">
      <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',padding:'10px 16px'}}>
        <button onClick={onBack} style={{background:'transparent',border:'none',padding:8,cursor:'pointer'}}>
          <VPIcon name="back" size={22}/>
        </button>
        <div style={{fontSize:15,fontWeight:500}}>Ricevuta da Marco</div>
        <button style={{background:'transparent',border:'none',padding:8,cursor:'pointer'}}>
          <VPIcon name="more" size={22}/>
        </button>
      </div>
      <div style={{padding:'8px 20px 20px',display:'flex',flexDirection:'column',gap:16}}>
        {/* photo */}
        <div style={{
          alignSelf:'center',width:200,aspectRatio:'0.66',background:'#f4ede1',
          borderRadius:8,padding:'14px 12px',transform:'rotate(-2deg)',
          boxShadow:'var(--vp-shadow-3)',
          fontFamily:'var(--vp-font-mono)',fontSize:8,color:'#3a2f24',
          display:'flex',flexDirection:'column',gap:4,
        }}>
          <div style={{textAlign:'center',fontWeight:700,fontSize:9}}>BANCA INTESA · BONIFICO</div>
          <div style={{borderBottom:'1px dashed #b8a784',margin:'4px 0'}}/>
          <div>Da: M. ROSSI</div>
          <div>A: E + G + L BIANCHI</div>
          <div>Causale: Affitto ottobre 2026</div>
          <div style={{borderBottom:'1px dashed #b8a784',margin:'4px 0'}}/>
          <div style={{textAlign:'right',fontWeight:700,fontSize:13}}>EUR 480,00</div>
          <div style={{fontSize:7,color:'#7a6852',marginTop:4}}>04/10/2026 · TRN 8826491</div>
        </div>

        <div className="vp-card" style={{padding:'14px 16px',display:'flex',gap:12,alignItems:'center'}}>
          <VPAvatar name="Marco" size={42} hue={20}/>
          <div style={{flex:1}}>
            <div style={{fontSize:15,fontWeight:500}}>Marco Rossi</div>
            <div style={{fontSize:12,color:'var(--vp-ink-3)'}}>Stanza Salvia · da gen 2025</div>
          </div>
          <button style={{background:'var(--vp-paper-2)',border:'none',width:36,height:36,borderRadius:'50%',cursor:'pointer'}}>
            <VPIcon name="message" size={16}/>
          </button>
        </div>

        <div className="vp-card" style={{padding:'4px 0'}}>
          <Row label="Causale" value="Affitto · ottobre 2026" suggested/>
          <Row label="Importo" valueEditable importo={importo} setImporto={setImporto}/>
          <Row label="Data bonifico" value="4 ottobre · 14:32"/>
          <Row label="Match con mese" value="Ottobre" badge="ok"/>
        </div>

        <div style={{display:'flex',alignItems:'flex-start',gap:10,padding:'4px 4px',color:'var(--vp-ink-2)',fontSize:13,lineHeight:1.5}}>
          <VPLeaf size={20}/>
          <div>Confermando, Marco riceverà una notifica e il mese di ottobre risulterà <b>pagato</b>.</div>
        </div>
      </div>
      <div style={{flex:1}}/>
      <div style={{padding:'14px 20px 24px',background:'var(--vp-paper)',borderTop:'1px solid var(--vp-paper-3)',display:'flex',gap:10}}>
        <button className="vp-btn vp-btn--ghost" style={{flex:1,height:48}}>Aggiusta</button>
        <button onClick={onConfirm} className="vp-btn vp-btn--primary" style={{flex:2,height:48,fontSize:15}}>
          <VPIcon name="check" size={18}/> Conferma
        </button>
      </div>
    </div>
  );
}

function Row({ label, value, valueEditable, importo, setImporto, suggested, badge }) {
  return (
    <div style={{display:'flex',alignItems:'center',padding:'14px 16px',borderBottom:'1px solid var(--vp-paper-3)'}}>
      <div style={{flex:1,fontSize:13,color:'var(--vp-ink-3)'}}>{label}</div>
      {valueEditable ? (
        <div style={{display:'flex',alignItems:'center'}}>
          <span style={{color:'var(--vp-ink-3)',marginRight:4}}>€</span>
          <input value={importo} onChange={e=>setImporto(e.target.value)} style={{
            width:70,border:'none',outline:'none',textAlign:'right',
            background:'transparent',fontSize:15,fontWeight:500,
            fontFamily:'var(--vp-font-mono)',color:'var(--vp-ink)',
          }}/>
        </div>
      ) : (
        <div style={{display:'flex',alignItems:'center',gap:8,fontSize:14,fontWeight:500}}>
          {value}
          {suggested && <span className="vp-badge vp-badge--neutral" style={{height:20,fontSize:11}}>suggerito</span>}
          {badge==='ok' && <VPIcon name="check" size={14} color="var(--vp-sage-deep)"/>}
        </div>
      )}
    </div>
  );
}

function ApproveDone({ onDone }) {
  return (
    <div style={{flex:1,height:'calc(100% - 54px)',display:'flex',flexDirection:'column',alignItems:'center',justifyContent:'center',padding:'40px 28px',textAlign:'center',gap:18}}>
      <div style={{width:96,height:96,borderRadius:'50%',background:'var(--vp-sage-soft)',display:'flex',alignItems:'center',justifyContent:'center'}}>
        <VPIcon name="check" size={44} color="var(--vp-sage-deep)" stroke={2.4}/>
      </div>
      <div className="vp-display" style={{fontSize:28}}>Pagato, ottobre.</div>
      <div style={{color:'var(--vp-ink-2)',fontSize:15,lineHeight:1.5,maxWidth:280}}>
        Abbiamo avvisato Marco. Ora la matrice di ottobre è completa per <b>4 inquilini su 5</b>.
      </div>
      <div className="vp-card" style={{padding:'14px 18px',display:'flex',alignItems:'center',gap:12,width:'100%',maxWidth:300}}>
        <VPEnvelope size={36}/>
        <div style={{flex:1,textAlign:'left'}}>
          <div style={{fontSize:13,fontWeight:500}}>Manca Yusuf</div>
          <div style={{fontSize:12,color:'var(--vp-ink-3)'}}>In attesa di approvazione</div>
        </div>
        <VPIcon name="chevron" size={16}/>
      </div>
      <button onClick={onDone} className="vp-btn vp-btn--ghost" style={{marginTop:'auto'}}>Chiudi</button>
    </div>
  );
}

window.ProtoApprovaRicevuta = ProtoApprovaRicevuta;
