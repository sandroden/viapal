# Viapal · operazioni lato inquilino

Documentazione delle funzionalità che ruotano intorno agli **inquilini**:
generazione degli addebiti (affitti + utenze), notifiche, riconciliazione
bancaria. Si concentra sui **punti di ingresso disponibili** (admin, action,
management command) e sulle **operazioni di manutenzione ordinaria**.

## 1. Modelli coinvolti

| Modello | App | Ruolo |
|---|---|---|
| `TenantProfile` | properties | anagrafica inquilino |
| `RoomAssignment` | properties | periodo di occupazione di una stanza (canone, validità) |
| `Contract` | properties | contratto di locazione (anagrafica, regime fiscale, default pagatore bollette) |
| `TenantCondominioRate` | billing | quota condominio a carico inquilini per contratto, storicizzata |
| `UtilityChargePeriod` | billing | periodo utenze (mensile o bimestrale) — ancora per bollette e conguagli |
| `UtilityBill` | billing | bolletta fornitore (luce/gas) |
| `AnnualUtilityCost` | billing | costo annuale (TARI) |
| `Receivable` | billing | **addebito unificato** verso l'inquilino: `causale ∈ {affitto, utenze, extra}` |
| `BankTransaction` | billing | bonifico/movimento bancario |
| `BankTransactionAllocation` | billing | allocazione M:N tra `BankTransaction` e `Receivable` (riconciliazione) |
| `Notification`, `Template`, `RegolaSollecito` | notifications | solleciti automatici |

## 2. Generazione Receivable

### 2.1 Affitto

La funzione di calcolo è `billing.calc.rent.genera_pagamenti_mese(anno, mese, force=False, persist=True, tenant_id=None)`:
- itera i `RoomAssignment` con overlap col mese
- per ciascuno calcola `competenza_da/competenza_a` reali (pro-rata se l'inquilino è entrato/uscito dentro al mese)
- importo = `(canone_mensile + quota_condominio_valida_a_competenza_da) × giorni_competenza / giorni_mese`
- chiave unica `(assignment, causale=affitto, competenza_da, competenza_a)` → idempotente
- `force=True` → sovrascrive l'esistente, **eccetto** i Receivable già allocati a `BankTransaction` (guardia integrità)
- `persist=False` → calcola e restituisce `simulazione[]` senza scrivere

**Tre punti d'ingresso** che usano la stessa funzione:

| Origine | Note |
|---|---|
| Admin · *Strumenti rapidi* → **Genera Receivable affitto (mese)** | pagina standalone con form (anno, mese, tenant, force, dry_run). URL: `/admin/billing/receivable/genera-affitto/`. |
| Admin · changelist `UtilityChargePeriod` → action **Rigenera Receivable affitto** | richiede la selezione di uno o più period (usati come "ancora": il period definisce il range di mesi su cui iterare). Stessa option `force/dry_run/tenant`. |
| CLI · `manage.py genera_rent_payments --anno YYYY --mese MM [--force]` | per generazioni puntuali da terminale / cron / CI. |
| CLI · `manage.py genera_storico [--dal YYYY-MM] [--al YYYY-MM] [--force]` | bulk per range di mesi. |

### 2.2 Utenze

La funzione di calcolo è `billing.calc.utility.calcola_conguaglio_periodo(period_id, persist=False, tenant_id=None)`:
- prende un `UtilityChargePeriod` e cerca le `UtilityBill` (luce/gas) con `data_emissione` nel periodo + gli `AnnualUtilityCost` validi (TARI)
- somma per voce, calcola i giorni di presenza dei `RoomAssignment` overlap col periodo
- ripartisce pro-rata sui giorni-persona, arrotondamento `ROUND_HALF_UP`
- **regola d'oro** (Sandro 2026-05-02): se nessuna bolletta luce/gas è collegata, il periodo viene saltato (nessun conguaglio "solo TARI")
- `persist=False` → restituisce le quote senza scrivere
- `tenant_id` → filtra le quote da persistere/restituire (per debug)

**Punti d'ingresso**:

| Origine | Note |
|---|---|
| Admin · changelist `UtilityChargePeriod` → action **Rigenera Receivable utenze** | selezione di uno o più period. Option `dry_run/tenant`. |
| CLI · `manage.py calcola_conguaglio --period <id>` | per un singolo period. |
| CLI · `manage.py genera_conguagli_storici --dal YYYY-MM [--al YYYY-MM]` | crea i `UtilityChargePeriod` **mensili** mancanti + lancia il calcolo su ognuno (transazione per period, gli errori non bloccano il batch). |

### 2.3 Receivable extra

Addebiti non legati al calendario standard: rimborsi pro-rata (uscita
anticipata), spese una-tantum, aggiustamenti. Si creano **a mano dall'admin**
(`Receivable` → Aggiungi, `causale = extra`). Per gli aggiustamenti d'uscita
esiste anche `billing.calc.rent.aggiustamento_uscita(assignment_id, data_uscita)`
(non esposto in UI: chiamabile da shell).

## 3. Riconciliazione bancaria

Modello: ogni `BankTransaction` può essere allocato a uno o più `Receivable`
via `BankTransactionAllocation` (M:N con importo).

- I `BankTransactionAllocation` aggiornano automaticamente lo stato del
  `Receivable` collegato (signal `_on_alloc_saved` in `billing/signals.py`):
  - allocato ≥ dovuto → `stato = pagato`
  - allocato > 0 ma < dovuto → resta `atteso` (parziale)
- Punto di ingresso principale: changelist `BankTransaction` → editor inline
  delle allocazioni. Autocomplete sui `Receivable` ancora `atteso`.
- Frontend: pagina `/p/riconciliazione/` (vista proprietario) per riconciliare
  in modo grafico per inquilino.

## 4. Sintesi punti d'ingresso

| Operazione | Admin | Action | CLI |
|---|---|---|---|
| Crea `UtilityChargePeriod` di un mese | "+ Aggiungi periodo utenze" | — | `genera_conguagli_storici` (anche bulk) |
| Genera Receivable affitto di un mese | *Strumenti rapidi* → Genera Receivable affitto | Rigenera Receivable affitto (sui period) | `genera_rent_payments`, `genera_storico` |
| Genera Receivable utenze di un periodo | — | Rigenera Receivable utenze (sui period) | `calcola_conguaglio` |
| Carica bolletta luce/gas | Aggiungi `Bolletta utenza` (può uploadare PDF) | "Imposta pagata da owner" / "Sincronizza Expense" | `carica_bollette_scanner`, `importa_utenze_da_xlsx` |
| Riconciliare un bonifico | Edit `BankTransaction` → inline allocazioni | — | — |
| Settlement annuale (fratelli) | *Strumenti rapidi* → Genera settlement annuale | — | `genera_settlement` |

## 5. Manutenzione ordinaria

Frequenza consigliata e modalità preferita.

### 5.1 Mensile · **inizio mese** (1° o 2° giorno)

**Obbligatorio**: creare il `UtilityChargePeriod` del mese e generare i
Receivable affitto. Senza questo, gli inquilini non hanno addebiti.

**Cron (consigliato)**:
```cron
# Ogni 1° del mese alle 06:00: crea period del mese corrente + genera affitti
0 6 1 * *   cd /path/viapal/backend && ENV=production uv run manage.py genera_conguagli_storici --dal $(date +\%Y-\%m) --al $(date +\%Y-\%m)
5 6 1 * *   cd /path/viapal/backend && ENV=production uv run manage.py genera_rent_payments --anno $(date +\%Y) --mese $(date +\%-m)
```

`genera_conguagli_storici` è idempotente (`update_or_create`), quindi rilanciarlo non duplica nulla.

**Manuale, in alternativa, dall'admin**:
1. *Pagamenti e bollette → Periodi utenze → + Aggiungi* (campi: `periodo_da = primo del mese`, `periodo_a = ultimo del mese`, lascia i default).
2. *Strumenti rapidi → Genera Receivable affitto (mese)* → scegli anno/mese, **dry-run** la prima volta per controllare, poi rilancia senza dry-run.

### 5.2 Su evento · **arrivo bolletta**

1. Carica la `Bolletta utenza` dall'admin (`Pagamenti e bollette → Bollette utenze → + Aggiungi`). Allega PDF, imposta fornitore, `prodotto`, `data_emissione`, `periodo_da/a`, `importo_totale`.
2. Aggancia la bolletta al `UtilityChargePeriod` corretto (l'admin del period ha l'inline `utility_bills` filter_horizontal — la selezioni dal lato del period).
3. Se la bolletta è pagata, imposta `pagata_da_owner` (oppure usa l'action `Imposta pagata da` che lo fa in bulk e crea l'`Expense` automaticamente).
4. Lancia l'action *Rigenera Receivable utenze* sul period (consigliato: prima con **dry-run** per controllare le quote). I Receivable utenze esistenti vengono aggiornati; quelli già allocati a `BankTransaction` sono **protetti** (vedi guardia allocations).

### 5.3 Su evento · **ingresso / uscita inquilino**

1. Aggiungi o modifica il `RoomAssignment` (admin `Profili inquilini` o `Stanze`, AjaxInline).
2. Se l'inquilino esce **a metà mese**: il `RoomAssignment` deve avere `valid_to = giorno_uscita`. La generazione affitto crea automaticamente un `Receivable` `is_aggiustamento=True` con importo pro-rata.
3. Rigenera gli affitti del/i mese/i interessati con `genera_rent_payments` o dalla pagina admin standalone (con `--force` solo se vuoi sovrascrivere; comunque i Receivable già allocati vengono preservati).

### 5.4 Su evento · **cambio quota condominio**

L'amministratore condominiale invia un nuovo importo (es. 90€/mese da gennaio):

1. Admin `Contract` → AjaxInline `TenantCondominioRate` → aggiungi nuova rate
   con `valid_from = data nuovo importo`, `valid_to = vuoto`.
2. **Importante**: la logica `_quota_condominio_per(competenza_da)` somma
   *tutte* le rate valide a quella data. Per evitare doppi addebiti, chiudi
   la rate precedente impostando `valid_to = giorno prima del nuovo`
   (o tieni le rate strettamente non sovrapposte nel tempo).
3. Rigenera gli affitti dei mesi futuri (i passati restano).

### 5.5 Annuale · **chiusura anno** (gennaio dell'anno successivo)

1. Verifica che tutti i Receivable dell'anno siano riconciliati (oppure
   chiusi come `insoluto`).
2. *Strumenti rapidi → Genera settlement annuale*: aggrega Receivable pagati
   + Expense in voci ledger pro-quota tra i tre fratelli. Vedi
   [`contabilita-fratelli.md`](contabilita-fratelli.md).

### 5.6 Su richiesta · **rigenerazione bulk storica**

Per ricaricare tutto da zero (es. dopo un import dati):

```bash
ENV=dev uv run manage.py genera_conguagli_storici --dal 2024-01 --al 2026-12
ENV=dev uv run manage.py genera_storico                 # genera affitti per range
```

Entrambi sono **idempotenti**. La guardia allocations protegge la coerenza
con la cassa.

## 6. Lato inquilino · UI dedicate

Il frontend Quasar (PWA) espone all'inquilino loggato:

- `/i/home` — dashboard inquilino: prossime scadenze, ultime ricevute, saldo
- `/i/addebiti` — elenco `Receivable` con causale/stato, dettaglio + ricevuta
- `/i/utenze` — quota utenze per mese con breakdown (luce/gas/TARI) e link al period
- `/i/profilo` — anagrafica, contatti, preferenze di notifica

Le notifiche push (PWA service worker) usano `notifications.RegolaSollecito`
+ `Template` (admin `Pagamenti e bollette → Notifiche e solleciti`). Le
regole vengono valutate da un task notturno (vedi `notifications/tasks.py`)
che marca i Receivable in ritardo e invia notifiche.

## 7. Documentazione correlata

- [`contabilita-fratelli.md`](contabilita-fratelli.md) — modello settlement /
  cassa virtuale tra i tre proprietari.
- `backend/CLAUDE.md` — convenzioni di progetto.
- `PLAN.md` — roadmap e fasi.
