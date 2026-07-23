# Reviewer "Architettura/Backend" — Fase 3

Panel adversariale su `docs/vista-unificata-conguaglio/DESIGN.md` (+ `mockup.html`).
Metodo: backward reasoning dal risultato voluto (una riga per fratello, per anno,
che concluda con un conguaglio azionabile e riconcili con il piano di rientro).

Codice consultato:
- `backend/apps/accounting/services/saldi_live.py` (calcola_saldi_correnti / verifica_quadratura / calcola_piano_rientro)
- `backend/apps/billing/dashboard_views.py` (ContoEconomicoView, DashboardProprietarioView.bilancio_proprietari)
- `backend/apps/accounting/serializers.py` (SaldoLiveSerializer, QuadraturaSerializer, PianoRientroVoceSerializer)
- `backend/apps/accounting/views.py` (action `saldi_live`)
- `backend/apps/properties/models/owner.py` (quote_attive_at)
- `frontend/src/router/routes.ts`

---

## Punteggio

**6.5 / 10** sulla solidità architetturale.

Il design è onesto e ben ragionato sul piano contabile (la derivazione §2 è
corretta e la scelta "azionabile = cassa = −saldi_live.totale" è giusta), ma
contiene **una incoerenza temporale strutturale non risolta**: mescola, nella
stessa riga e nella stessa formula, grandezze calcolate su due basi temporali
diverse (anno solare vs periodo aperto live). È un problema di DATI, non solo di
UX come lo derubrica il doc. Riuso serializer parzialmente sovrastimato. Nessun
blocco di modello/migrazione: la superficie di implementazione è piccola e il
refactor è fattibile.

---

## Findings

### F1 — [PLAN_RISK] P1 — `conguaglio_cassa` per-anno vs `−saldi_live.totale` live: non riconciliano (mandato 1 e 5)
§2.3, §5.2, §5.3 (`fratelli[].conguaglio_cassa`) — `saldi_live.py:85-114`

Il cuore del design contiene una contraddizione:

- §5.3 dichiara, nel commento del campo, `conguaglio_cassa = cassa_netta −
  q·utile_cassa = −saldi_live.totale`.
- Ma `cassa_netta` (`I_o − A_o`) e `utile_cassa` sono grandezze **per anno
  solare** (§5.2: `I_o/A_o` dalla logica di `bilancio_proprietari` filtrata
  `data_pagamento__year=anno`; `utile_cassa` da `ContoEconomicoView` filtrato
  per anno).
- `−saldi_live.totale`, invece, è calcolato da `calcola_saldi_correnti(oggi)`
  sul **periodo aperto live** (`saldi_live.py:96` → `periodo_da` = giorno dopo
  l'ultimo `OwnerSettlement`, fino a `oggi`), e include `baseline_settlement`
  (`:102,171`) e `bt_inter_owner` (`:165-168`).

L'identità `−saldi_live.totale = cassa_netta − q·utile_cassa` regge **solo** nel
caso degenere: anno == periodo aperto, nessun settlement di baseline precedente,
nessuna BT inter-owner, nessun `riferimento_quota_owner`. È esattamente il caso
dell'esempio §3.1, che perciò "torna" e nasconde il problema. In produzione
(un settlement passato, o l'anno selezionato ≠ anno corrente) i due numeri
divergono e **la riga non chiude la propria aritmetica**: la colonna
`conguaglio_cassa` (se presa da saldi_live) non è più uguale a `cassa_netta −
scarto_timing − q·utile_comp` mostrata a fianco.

Il design lo tratta come "rischio UX" (§7.4): è invece incoerenza di DATI. La
somma-zero della colonna si conserva (saldi_live somma zero), ma la
**riconciliazione orizzontale della singola riga** salta. Va risolto scegliendo
una sola base per l'intera riga (vedi F5), non giustapponendo le due.

### F2 — [EXISTING] P1 — Basi di cassa diverse: saldi_live NON filtra per causale, bilancio_proprietari sì
`saldi_live.py:107-114` vs `dashboard_views.py:392-397`

`calcola_saldi_correnti` costruisce `rec_qs` con `stato=PAGATO` + filtro data,
**senza filtro `causale`** (righe 107-114): include quindi i Receivable
`DEPOSITO`. La logica `bilancio_proprietari` che il design propone come fonte di
`I_o` (§5.2) filtra `causale__in=CAUSALI_OPERATIVE` (`:396`), che **esclude
DEPOSITO** (commento `dashboard_views.py:49`). Quindi anche a parità di periodo,
`I_o` dalla logica bilancio e la componente incassi di `−saldi_live.totale`
usano **insiemi di Receivable diversi**. Ulteriore ragione per cui
`conguaglio_cassa` derivato da saldi_live non uguaglia `cassa_netta` costruita
dal bilancio. Se si vuole l'identità dichiarata, le due sorgenti vanno
allineate (o si esplicita che il deposito è dentro/fuori e perché).

### F3 — [PLAN_RISK] P1 — Scoping `?anno=YYYY` su saldi_live è impossibile con la firma attuale (mandato 5)
§5.1, §7.4 — `saldi_live.py:67-71, 85-96`

`calcola_saldi_correnti(at_date)` accetta solo una **data**, non un periodo: il
`periodo_da` è imposto dall'ultimo settlement (`_ultimo_settlement`), non
parametrizzabile. Non esiste alcun modo di ottenere "il conguaglio di cassa del
solo 2024" salvo che esista un `OwnerSettlement` esattamente ai confini
d'anno. Per un anno **passato o chiuso** il `piano_rientro` esposto sotto il
selettore "Anno 2024" sarebbe in realtà il piano **live a oggi** del periodo
aperto — potenzialmente multi-anno — cioè un dato scollegato dall'anno mostrato.
La mitigazione del doc ("è un'etichetta") non è una soluzione: è etichettare un
numero con l'anno sbagliato. Soluzione adeguata: introdurre in `saldi_live` un
parametro di periodo esplicito (`periodo_da`/`periodo_a` o `at` + `da`),
**oppure** limitare la colonna azionabile al solo periodo aperto corrente e
rendere gli anni chiusi read-only da snapshot `OwnerSettlement` (che il design
già cita al §7.4 ma non collega alla shape). Senza uno dei due, l'endpoint per
`anno ≠ periodo aperto` restituisce un piano non pertinente.

### F4 — [PLAN_RISK] P1/P2 — Colonne descrittive I_o/A_o/cassa_netta contraddicono il conguaglio derivato quando c'è `riferimento_quota_owner` (mandato 4)
§7.3, §5.3, mockup righe 168-172 — `saldi_live.py:138-149`

La regola §7.3 ("derivare l'azionabile da saldi_live, non ricostruirla") è
giusta e rispettata nella scelta della fonte. Ma la shape §5.3 mette nella
**stessa riga** `cassa_netta` (da I_o/A_o pro-quota) e `conguaglio_cassa` (da
saldi_live) e il mockup mostra `conguaglio` come se derivasse da `cassa_netta`
(subval "25.000 − 5.000"). Quando esiste una spesa con `riferimento_quota_owner`
(es. Bruna paga IMU di Fabio), saldi_live la tratta **fuori pro-quota** come
credito intero verso il referente (`:138-149`), mentre le colonne descrittive
`A_o`/`cassa_netta` la contano pro-quota. Risultato: la relazione
`conguaglio_cassa = cassa_netta − q·utile_cassa` **stampata nella riga è falsa**
in presenza di quel caso, e le colonne descrittive contraddicono visivamente il
conguaglio. Va gestito: o si marca esplicitamente lo scostamento
(riga "rettifiche fuori pro-quota"), o si rinuncia a suggerire nella UI che il
conguaglio discende dalle colonne a sinistra.

### F5 — [PLAN_RISK] P2 — La riga vuole essere insieme "anno" e "live": scelta architetturale non fatta
§3, §5.2-5.3

Conseguenza sintetica di F1/F3/F4. Il design deve decidere, e dichiararlo nella
shape, UNA sola natura per la colonna azionabile:
- **(A) tutto-anno**: ricalcolare `conguaglio_cassa` come `cassa_netta_anno −
  q·utile_cassa_anno`. Coerente con la riga, ma §7.3/§8 lo vietano perché perde
  baseline settlement, BT inter-owner e `riferimento_quota_owner`, e non è più
  ciò che si bonifica oggi.
- **(B) tutto-live**: `conguaglio_cassa = −saldi_live.totale` e piano dal
  periodo aperto. Coerente col denaro reale, ma **non è un dato d'anno**: allora
  `scarto_timing` e `utile_spettante_competenza` (che SONO per anno) non
  appartengono alla stessa riga e vanno separati in un blocco "competenza/anno"
  distinto dal blocco "conguaglio/live".

Il doc oggi mescola A e B nella stessa tabella. Raccomando (B) con separazione
netta dei due blocchi e il piano live etichettato "dovuto a oggi", riservando la
riga d'anno alla sola competenza. È l'unico assetto che non introduce numeri che
non riconciliano.

### F6 — [PLAN_RISK] P2 — Riuso serializer sovrastimato: `SaldoLiveSerializer` NON serve la shape `fratelli[]`
§5.3 (nota "SaldoLiveSerializer … riusabile") — `serializers.py:103-116`

`SaldoLiveSerializer` serializza la **decomposizione** di `SaldoLive` (`owner`,
`incassi_per_causale`, `spese_per_categoria`, `anticipi_pendenti`,
`bt_inter_owner`, `totale`). Non ha nessuno dei campi della riga proposta
(`utile_spettante_competenza`, `incassato`, `anticipato`, `cassa_netta`,
`scarto_timing`, `conguaglio_cassa`, `conguaglio_competenza`, `verso`). Quindi
`fratelli[]` richiede un **serializer nuovo**: la riusabilità dichiarata è vera
solo per `PianoRientroVoceSerializer` (`:145-149`, shape identica a §5.3
`piano_rientro`) e — con un remap — `QuadraturaSerializer`. Non è un blocco, ma
il "massimo riuso" del §5 va ridimensionato: il pezzo owner-centrico è tutto
nuovo (calcolo + serializer).

### F7 — [PLAN_RISK] P3 — `QuadraturaSerializer` non serve la shape `quadratura` così com'è
§5.3 (`quadratura.conguaglio_cassa_somma`) — `serializers.py:137-142`

Il serializer espone `somma_saldi`; la shape §5.3 usa `conguaglio_cassa_somma`.
Sono lo stesso numero a segno invertito (Σ saldi = 0 ⇒ irrilevante il segno),
ma la chiave differisce: serve un wrapper/remap, non il serializer as-is. Minore,
ma smentisce il "riusabile" letterale.

### F8 — [PLAN_RISK] P2 — Refactor `calcola_blocchi(anno)` deve restituire più di `{cassa, competenza}` (mandato 2)
§5.2 — `dashboard_views.py:699-745, 819-828`

L'estrazione è fattibile e sensata (i due loop ricavi + separazione
ord/straord sono autocontenuti). Ma `ContoEconomicoView` calcola nel loop
competenza anche `non_incassato`, `non_incassato_voci`, `insoluti`
(`:701-719`) che finiscono nella risposta **fuori** da `_blocco` (`:823-828`).
Se l'helper firma `-> {cassa, competenza}` e basta, `ContoEconomicoView`
regredisce (perde quei campi) oppure duplica di nuovo il loop competenza — cioè
l'opposto dello scopo. La firma deve restituire anche i sotto-totali di
competenza (o un dataclass ricco). Inoltre `I_o/A_o per owner` **non** vivono in
`ContoEconomicoView` ma in `DashboardProprietarioView` (`:374-430`): fattorizzare
tocca una **seconda** view. Refactor gestibile ma con due punti di regressione;
va coperto da caratterizzazione (esiste già `test_saldi_live.py`; verificare che
esistano test su ContoEconomico prima di toccarlo). Regressione più probabile:
drift silenzioso tra la vecchia `_blocco` inline e il nuovo helper se non si
sostituisce anche la chiamata originale.

### F9 — [PLAN_RISK] P2 — `conguaglio_competenza` nel payload: rischio "qualcuno lo bonifica" (mandato 3)
§5.3, §8

Il campo `conguaglio_competenza` (non zero-sum) nel JSON è un rischio concreto:
un client (o un futuro sviluppatore FE) può leggerlo e proporlo come importo da
versare, reintroducendo esattamente la confusione cassa/competenza che il
progetto ha faticato a separare (memorie `viapal_sbilancio_reale`,
`viapal_credito_pagamento_unico`). Il doc lo sa (§8) ma **lo espone lo stesso**
in un array che sembra parallelo a `conguaglio_cassa`. Mitigazione minima:
NON metterlo come sibling di `conguaglio_cassa`; annidarlo sotto un oggetto
`contesto`/`informativo` (es. `fratelli[].informativo.conguaglio_competenza`)
così che nessuna colonna azionabile possa puntarlo per errore, e chiarire in
docstring che non è un importo bonificabile. Severità contenuta perché read-only
e non genera scritture, ma è un foot-gun API.

### F10 — [EXISTING] P3 — Permessi e validazione anno: OK come dichiarato
§5.1 — `dashboard_views.py:669,686-688`; `accounts/permissions.IsProprietario`

`IsProprietario` esiste ed è già usato da `ContoEconomicoView`/
`DashboardProprietarioView`. Il pattern di validazione `anno`
(`int(...)` + try/except → 400, default `oggi.year`) è replicabile 1:1 da
`ContoEconomicoView`. Nessun problema. Nota minore: `ContoEconomicoView` NON
valida che l'anno sia in un range sensato (accetta 1 o 9999); il nuovo endpoint
erediterebbe la stessa mancanza — accettabile ma da tenere presente se il
selettore FE è libero.

### F11 — [EXISTING] P3 — Zero-sum e arrotondamenti: assunzione corretta
§3.1, §7.5 — `saldi_live.py:256-277`

La delega dello zero-sum e dell'assorbimento centesimi al `calcola_piano_rientro`
(greedy a due puntatori, quantize 0.01, residuo sull'ultimo trasferimento) è
corretta e già collaudata. La tabella d'esempio §3.1 quadra. Nessun rilievo,
salvo che il "0,00" di totale conguaglio in tabella vale solo se la colonna è la
versione live (F1): se fosse ricostruita per anno con quote riproporzionate
(`quote_attive_at` ribilancia, owner.py:32-37) lo zero-sum resta ma può divergere
dal piano live.

---

## Verdetto

Design contabilmente solido e con la scelta giusta sull'azionabile (cassa =
−saldi_live.totale), ma **non ha risolto la scelta architetturale tra base
"anno" e base "live"**: le espone entrambe nella stessa riga con una formula che
riconcilia solo nel caso degenere dell'esempio — va spezzato in due blocchi
(competenza/anno vs conguaglio/live) e saldi_live va reso period-aware prima di
poter reggere il selettore anno.
