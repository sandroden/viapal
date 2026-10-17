# Video demo Viapal — storyboard

Pubblico: proprietari che potrebbero provare Viapal gratis. Formato desktop
1920x1080, 30 fps, italiano, nessuna voce: didascalie a schermo. Durata
obiettivo ~2'45". Dati: db `viapal_demo` anonimizzato (importi x0,7, Novara),
utente `massimo`, immobile "Casa dei Tigli" (a stanze).

Le clip si girano con `riprese/scene/NN-*.sh` (richiede `just demo`), finiscono
in `public/clips/` e si montano in Remotion (`src/`). Le durate sono indicative:
il montaggio può accelerare i tratti morti.

| # | Scena | Durata | Didascalia | Azione |
|---|---|---|---|---|
| — | Apertura | 6 s | **Affitti a stanze, senza fogli Excel.** | cartello Remotion, logo |
| 01 | Cruscotto | 12 s | Tutto l'anno a colpo d'occhio: incassi, spese, ritardi. | `/p/`: indicatori, scroll a ritardi ed entrate/uscite |
| 02 | Inquilini | 14 s | Ogni inquilino: contratto, pagamenti, documenti. | `/p/inquilini` → scheda di un inquilino attivo → tab Pagamenti e Documenti |
| 03 | Utenze | 30 s | Carichi la bolletta: importi e periodo letti in automatico. / Divisa per i giorni di presenza di ciascuno. / Ognuno riceve il suo conto. | `/p/utenze` su un mese chiuso: passo 1 bollette, passo 2 ripartizione con grafico, passo 3 anteprima email; tab Andamento |
| 04 | Lato inquilino | 18 s | L'inquilino vede quanto deve e paga con un QR. | "Vedi come questo inquilino" → home → Paga con bonifico (QR) → Utenze → Torna a te |
| 05 | Riconciliazione | 18 s | Bonifici abbinati agli addebiti in due clic. | `/p/riconciliazione`: clic su un bonifico, addebiti filtrati, spunta, residuo 0,00 → Annulla |
| 06 | Ritardi e solleciti | 12 s | Chi è in ritardo, e un sollecito pronto da inviare. | `/p/ritardi` → `/p/notifiche`: anteprima email di riepilogo |
| 07 | Spese e conto economico | 18 s | Spese e conto economico, per cassa o per competenza. | `/p/spese` grafico + dialog Aggiungi (annullato) → `/p/conto-economico` Cassa→Competenza, occupazione camere |
| 08 | Saldi proprietari | 10 s | Più proprietari? Chi ha anticipato cosa, e chi deve a chi. | `/p/saldi-proprietari` |
| 09 | Annuncio pubblico | 15 s | Un annuncio pronto da condividere. | `/g/<slug>`: foto, planimetria con numeri, foto delle camere |
| 10 | Cerca inquilini | 10 s | I contatti da Facebook e Subito, già riassunti. | `/p/cerca-inquilini` → Statistiche |
| 11 | Documenti generati | 12 s | Atto di subentro e cessione di fabbricato, compilati dai dati. | scheda inquilino → Documenti → Genera → riepilogo (Annulla) |
| 12 | Più immobili | 8 s | A stanze o appartamento intero, anche più d'uno. | cambio immobile dall'intestazione, "Nuova proprietà" |
| — | Chiusura | 6 s | **Prova Viapal gratis.** + contatto | cartello Remotion |

## Regole di ripresa

- Nessun salvataggio: dialog e anteprime si aprono e si chiudono con Annulla,
  così il db demo resta uguale e ogni scena si rigira identica.
- Movimenti del cursore deliberati, pausa di ~2,5 s sui punti in cui cade una
  didascalia; niente scatti di pagina non motivati.
- Elementi da sviluppo e banner nascosti da `riprese/scena.js`.
