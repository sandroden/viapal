# Reviewer "Correttezza/Algebra Hawk" — Phase 3

Target: `docs/vista-unificata-conguaglio/DESIGN.md` (+ `mockup.html`), verificato
contro il codice reale `backend/apps/accounting/services/saldi_live.py`,
`backend/apps/billing/dashboard_views.py`, `backend/apps/properties/models/owner.py`.

Legenda severità: P0 (rompe la correttezza / va corretto prima di procedere),
P1 (difetto sostanziale, il design ci ragiona ma l'esempio lo maschera),
P2 (imprecisione / trappola d'implementazione), P3 (cosmetico / nota).
`[EXISTING]` = fatto verificato sul codice attuale. `[PLAN_RISK]` = rischio della
proposta non ancora implementata.

---

## Punteggio: 8.5 / 10 (solidità matematica)

Le tre derivazioni algebriche centrali (§2.2, §2.3, §2.4) sono **corrette e
combaciano riga-per-riga col codice**. La tabella d'esempio §3.1 è
**aritmeticamente esatta in ogni cella** (ricontrollata con `Decimal`, zero drift).
Il punteggio non è 10 perché il documento presenta come **identità piana**
(`conguaglio_cassa = −saldi_live.totale`) una relazione che è esatta **solo** nel
caso pulito (niente baseline settlement, niente BT inter-owner, e periodo aperto
== anno solare). L'esempio §3.1/§3.2 è costruito proprio in quel caso pulito e
quindi *nasconde* la tensione che invece §5.2/§7/§8 riconoscono a parole ma non
riconciliano numericamente. Chi implementa seguendo l'esempio, non la prosa,
rischia una colonna azionabile che non torna col piano di rientro.

---

## Findings

### F1 — §2.2 derivazione `saldi_live.totale` — CORRETTA [EXISTING] (nessun errore)
Verifica contributo incassi e spese contro `calcola_saldi_correnti`:

- Incassi, owner incassante: codice `-(1 - quota)*importo`
  (`saldi_live.py:123`); altrui `+quota*importo` (`:126`).
  Somma su tutti gli incassi per `o`:
  `-(1-q_o)·I_o + q_o·(I_tot-I_o) = q_o·I_tot − I_o`. **Identico a §2.2.**
- Spese, owner anticipante: `(1 - quota)*importo` (`:152`); altrui
  `-quota*importo` (`:155`). Somma: `(1-q_o)·A_o − q_o·(A_tot−A_o) = A_o − q_o·A_tot`.
  **Identico a §2.2.**
- Totale (`saldi_live.py:170-176`, prima di baseline/BT):
  `q_o·(I_tot−A_tot) − (I_o−A_o) = q_o·utile_cassa − cassa_netta(o)`. **§2.2 ok.**

Segni e convenzione creditore(+)/debitore(−) coerenti col docstring (`:22-25`) e
col `piano_rientro` (`:257-258`: creditori `totale ≥ cent`, debitori `≤ -cent`).

### F2 — §2.3 identità `conguaglio_cassa = −saldi_live.totale` — VERA MA PARZIALE [PLAN_RISK] — P1
Algebricamente `−(q_o·utile_cassa − cassa_netta) = cassa_netta − q_o·utile_cassa`:
esatta. **Ma `saldi_live.totale` reale NON è solo quel termine.** Da
`saldi_live.py:170-176`:

```
totale = baseline_settlement + Σincassi + Σspese + bt_inter_owner
```

Quindi `−saldi_live.totale = (cassa_netta − q·utile_cassa) − baseline − bt_inter_owner`.
Il §2.2 dichiara onestamente "ignorando baseline settlement, BT inter-owner", ma
§2.3, la tabella §3.1 e il commento JSON §5.3
(`"conguaglio_cassa": ... = -saldi_live.totale`) riscrivono l'identità **piana**,
senza i due termini. Non è falsa: è vera **solo** quando baseline=0 e bt=0.
Il design la usa nel modo giusto altrove (§2.6/§8: "derivare da `saldi_live`, non
ricostruire"), quindi il *rischio* è che l'implementatore prenda la formula
scritta (`cassa_netta − q·utile_cassa`) invece dell'oggetto `saldi_live.totale`.
**Azione richiesta:** in §2.3 e nel JSON annotare esplicitamente
`= −saldi_live.totale` **includendo** baseline+BT, e marcare la formula
`cassa_netta − q·utile_cassa` come valida solo nel caso pulito.

### F3 — Zero-sum §2.3 — REGGE sotto assunzioni esplicite [EXISTING/PLAN_RISK] — P1
`Σ conguaglio_cassa = Σcassa_netta − (Σq)·utile_cassa`. Zero **iff**:
1. `Σ q_o = 1` — garantito da `quote_attive_at` che riproporziona
   (`owner.py:32-37`). ✔
2. `Σ cassa_netta = utile_cassa`, cioè `I_tot − A_tot` calcolato **sugli stessi
   record** che entrano in `cassa_netta`. **Qui c'è la trappola (F5).**
3. Niente orfani (Receivable PAGATO senza incassante, anticipante senza quota):
   `verifica_quadratura` (`saldi_live.py:181-245`) li porta a galla; §7.6 lo
   recepisce. ✔ (dichiarato non-quadrante, corretto).
4. baseline/BT: se presenti, la colonna azionabile deve essere `−saldi_live.totale`
   (che li include) e **non** la formula pulita, altrimenti la somma non è più il
   trasferibile reale (F2). Il §7.3 (`riferimento_quota_owner`,
   `saldi_live.py:138-149`) e §7.4 (baseline) lo colgono correttamente.

### F4 — Mismatch di PERIODO annuale-vs-live — [PLAN_RISK] — P1 (il più insidioso)
`saldi_live` è **scoped al periodo aperto** (dal giorno dopo l'ultimo settlement,
`_ultimo_settlement` `saldi_live.py:67-71`, filtri `periodo_da` alle righe
113-114/132-133/162-163). La tabella conguaglio è **per anno solare** (§4, §5.2
usa `data_pagamento__year=anno`). Quindi:

- Colonna `conguaglio_cassa` proposta = `cassa_netta(anno) − q·utile_cassa(anno)`
  → finestra = anno solare.
- `piano_rientro` proposto (§5.2, §3.2) = `calcola_piano_rientro(saldi_live(oggi))`
  → finestra = periodo aperto (può essere multi-anno o parte d'anno).

**Sono due finestre diverse.** L'affermazione §3.2 «Coincide con l'output di
`calcola_piano_rientro` sui saldi live (segni invertiti)» è vera **solo** se il
periodo aperto coincide con l'anno (ultimo settlement al 31/12 anno-1 e nessun
movimento futuro). L'esempio §3.1 è costruito così e quindi maschera il caso
generale: negli anni reali la colonna annuale e il piano live **non torneranno**.
Il §5.2 lo ammette a parole ("il piano azionabile è quello del periodo aperto
live … la tabella è riconciliazione/contesto"), ma non c'è alcuna verifica che
`Σ conguaglio_cassa(anno)` coincida col `Σ` del piano live. **Azione:**
separare esplicitamente due grandezze con nomi diversi (`conguaglio_anno` vs
`saldo_live_oggi`) e NON promettere che coincidano; oppure derivare la colonna
azionabile dallo stesso `saldi_live(oggi)` filtrato, rinunciando all'annualità
della colonna azionabile.

### F5 — Universo-sorgente `utile_cassa` vs `cassa_netta` divergente — [PLAN_RISK] — P2
§5.2 prende `utile_cassa` da `ContoEconomicoView` e `cassa_netta` da
`bilancio_proprietari`. **Universi diversi:**

- `ContoEconomicoView.ricavi_cassa` (`dashboard_views.py:692-697`): tutti i
  PAGATO dell'anno, **senza** filtro su `incassato_da_owner`. Spese
  `tot_ord+tot_straord` (`:724-730`): **tutte** le Expense dell'anno, senza
  filtro anticipante.
- `bilancio_proprietari` (`:392-409`): solo Receivable con
  `incassato_da_owner__isnull=False` (`:395`) e solo Expense con
  `anticipata_da_owner_id` valorizzato (`:405`).

Se esistono orfani (record non attribuiti), `Σ cassa_netta ≠ utile_cassa`,
quindi `Σ conguaglio_cassa ≠ 0` **e** la colonna `scarto_timing` (che usa
`utile_cassa` "pieno") diventa incoerente con `cassa_netta` (attribuito). §7.6
segnala la non-quadratura, ma la **causa** (due universi) non è chiamata per nome.
**Azione:** per lo zero-sum usare `I_tot = Σ I_o attribuiti` (stesso universo di
`cassa_netta`), non `ricavi_cassa` di ContoEconomico; oppure derivare tutto da
`saldi_live` (coerente con la raccomandazione §8).

### F6 — §2.4 "le spese si semplificano, scarto tutto lato ricavi" — CONFERMATO [EXISTING] — nessun errore
Verificato su `ContoEconomicoView._blocco` (`dashboard_views.py:732-745`):
`tot_ord` e `tot_straord` sono calcolati **una sola volta** da
`Expense.filter(data__year=anno)` (`:721-730`) e **riusati identici** sia per
`blocco_cassa` sia per `blocco_comp`. Quindi
`utile_cassa − utile_comp = ricavi_cassa_tot − ricavi_comp_tot`: le spese si
cancellano esattamente. **Affermazione §2.4 corretta.** (docstring conferma:
`:663-664` "Le spese sono per data … in entrambe le letture".)

### F7 — `scarto_timing ≠ −non_incassato` in generale — [PLAN_RISK] — P2
§2.4/§5.3 equiparano lo scarto al `non_incassato` (JSON: `scarto_timing:-3000`,
`non_incassato:3000`, esatti opposti). Ma `scarto = ricavi_cassa − ricavi_comp`
(F6) contiene **due** direzioni:
- ricavi di competenza dell'anno non ancora incassati (`non_incassato`,
  `dashboard_views.py:701-719`), e
- incassi dell'anno la cui **competenza è in un altro anno** (es. affitto 2025
  pagato a gennaio 2026: entra in `ricavi_cassa[2026]` ma non in
  `ricavi_comp[2026]` — cfr. `_competenza_base` `:708-709`).

Solo se non ci sono incassi cross-anno lo scarto = −`non_incassato`. Il JSON che
li mette come opposti esatti è vero solo in quel sotto-caso. **Azione:** definire
`scarto_timing := ricavi_cassa − ricavi_comp` e trattare `non_incassato` come
*una delle* componenti, non come l'intero.

### F8 — Tabella §3.1 — ARITMETICA ESATTA [verificata con Decimal] — nessun errore
Ricalcolo `Decimal` (nessun arrotondamento intermedio):

| Fratello | q | utile_spett(comp) | cassa_netta | scarto | cong_cassa | cong_comp |
|---|---|---|---|---|---|---|
| Ale | 0.3334 | 10002.00 | 20000 | −1000.20 | **+10998.20** | +9998.00 |
| Bruna | 0.3333 | 9999.00 | 4000 | −999.90 | **−4999.10** | −5999.00 |
| Fabio | 0.3333 | 9999.00 | 3000 | −999.90 | **−5999.10** | −6999.00 |
| Σ | 1.0000 | 30000.00 | 27000 | **−3000.00** | **0.00** | −3000.00 |

Tutte le verifiche del doc reggono: `Σ cassa_netta = 27000 = utile_cassa` ✔;
`Σ cong_cassa = 0` ✔; `Σ scarto = −3000 = utile_cassa−utile_comp` ✔;
`Σ cong_comp = −3000 ≠ 0` ✔ (giustamente non azionabile). Piano §3.2:
Ale→Fabio 5999.10 + Ale→Bruna 4999.10 = 10998.20 = debito Ale ✔, e coerente col
greedy `calcola_piano_rientro` (`saldi_live.py:248-277`: max debitore paga
creditori in ordine decrescente → Fabio 5999.10 prima di Bruna 4999.10). **Zero
errori aritmetici.** Nota: l'esempio è però *cherry-picked* — quote 4-decimali e
importi che rendono `q·utile_cassa` esatto al centesimo (0.3334·27000=9001.80,
0.3333·27000=8999.10). Non stressa gli arrotondamenti (vedi F9).

### F9 — §7.5 arrotondamenti / "assorbe centesimi ultimo bonifico" — IMPRECISO [EXISTING] — P3
`calcola_piano_rientro` (`saldi_live.py:256-277`) **quantizza ogni `totale`
indipendentemente** a `0.01` (`:257-258`) prima del greedy, poi assegna
`min(debitore, creditore)` (`:265`). `verifica_quadratura` invece quantizza la
**somma** (`:241`). Se i totali hanno componenti sub-centesimo, la somma dei
creditori quantizzati può differire da quella dei debitori quantizzati: il greedy
**tronca** il residuo (< 1 cent) lasciandolo non assegnato quando un lato si
esaurisce — **non** lo "assorbe sull'ultimo trasferimento" come dice §7.5. È
innocuo (< 1 cent) ma la descrizione è ottimistica. **Azione:** riformulare "il
residuo sub-centesimo resta non bonificato ed emerge dalla Quadratura", che è ciò
che il codice fa davvero (`:253-255` docstring lo conferma: "il residuo emerge
dalla Quadratura, non da qui").

### F10 — mockup: inversione colore segno conguaglio — NOTA [PLAN_RISK] — P3
`mockup.html:172` mostra `+10998,20` (versa) con classe `neg` (rosso terra) e
`:181/:190` i negativi (riceve) con classe `pos` (verde). Scelta deliberata
(versa = esborso = rosso per il fratello), non un errore algebrico, ma il **segno
numerico è opposto al colore**: `+` in rosso, `−` in verde. Da documentare in UI
per non confondere con la convenzione `saldi_live` (dove `+` = creditore).
Coerente col badge "versa"/"riceve", quindi accettabile; segnalo solo la
potenziale dissonanza segno↔colore.

---

## Verdetto

Algebra centrale corretta e verificata sul codice, tabella esatta al centesimo;
il rischio reale non è nei numeri ma nel presentare come identità piana una
relazione valida solo nel caso pulito e nel confondere due finestre temporali
(anno vs periodo aperto) e due universi-sorgente (ContoEconomico vs
bilancio_proprietari) — da separare esplicitamente prima di implementare.
