---
type: Feature
title: Lead — ricerca inquilini
description: I contatti trovati dal bot Facebook depositati su viapal e lavorati in due da /p/cerca-inquilini.
resource: backend/apps/leads/models.py
resources:
  - backend/apps/leads/models.py
  - backend/apps/leads/serializers.py
  - backend/apps/leads/views.py
  - frontend/src/pages/ProprietarioLeads.vue
  - frontend/src/stores/leads.ts
tags: [feature, leads, campagna, bot, gdpr]
timestamp: 2026-09-05T00:00:00Z
---

# Overview

Quando le stanze sono sfitte, un bot (codice in `bot/` di questo repo, in
origine un worktree separato) legge i gruppi Facebook degli affitti di Monza, classifica i
post di chi cerca stanza e prepara i due messaggi di risposta. Notificava su
Telegram e basta: buono per chi ha il telefono in mano, inutile per lavorare in
due — non diceva a chi era già stato scritto.

L'app `leads` è il **secondo binario**: gli stessi contatti depositati qui, e
lavorati dalla pagina **Cerca inquilini** (`/p/cerca-inquilini`).

Non è anagrafica. È lo stato di una **campagna**: dura le due settimane di
sfitto e poi si cancella (vedi *Chiusura di campagna*).

# L'invariante: due metà con proprietari diversi

`Lead` contiene sia quello che ha trovato il bot sia quello che fanno le
persone, e le due metà non si toccano:

| metà | campi | chi li scrive |
|---|---|---|
| scoperta | `testo`, `author_*`, `permalink`, `link_messenger`, `analisi`, `commento_proposto`, `privato_proposto`, `seen_at`, `group_*` | il bot, a ogni upsert dello stesso post |
| lavorazione | `stato`, `preso_da`, `preso_at`, `contattato_at`, `note`, `foto` | le persone, dalla pagina |

L'upsert del bot **non tocca mai** la seconda metà. La garanzia non è la buona
educazione del payload: sono **due serializer** (`LeadBotSerializer` e
`LeadLavorazioneSerializer`) e i campi dell'altra metà non esistono nemmeno
come nome. Unificarli significa che il secondo passaggio dello scraper sullo
stesso post cancella il fatto che a quella persona è già stato scritto.

Chiave dell'upsert: **`(property, post_id)`**, non `post_id` globale — due
immobili che pescano dallo stesso gruppo devono poter lavorare lo stesso post,
ognuno con la propria presa in carico.

`analisi.stanze_compatibili` contiene gli id di configurazione del bot
(`"S2"`), non PK di `Room`: restano testo dentro il JSON.

**`foto`** (dal 2026-08-29, migrazione `0002_lead_foto`): il ritratto preso dal
profilo, incollato a mano (Ctrl-V col puntatore sopra, clic o trascinamento)
per riconoscere la persona fra annunci quasi identici. È una **colonna
`TextField` con data-URI**, non un `FileField`: `chiudi_campagna` cancella i
lead in blocco senza signal, e un file su storage sopravviverebbe alla
cancellazione promessa. Il browser ritaglia al centro e riduce a 128 px (~1,5
kB WebP); il validatore `valida_fotina` (prefisso data-URI + lunghezza massima)
vale anche per un PATCH da curl. È un campo umano come `note`: il bot non lo
nomina e l'upsert non lo azzera.

# Endpoint

- `POST /leads/bulk-upsert/` — il bot. `IsPropertyMember` +
  `BasicAuthentication` (è uno script, non ha sessione da cui prendere il
  CSRF): stesso schema del bulk-import dei movimenti bancari. Idempotente.
- `GET /leads/` — lista filtrabile per `stato`, `gruppo`, `preso_da`
  (`me`/`nessuno`/id).
- `PATCH /leads/<id>/` — solo `stato`, `note` e `foto`
  (`LeadLavorazioneSerializer`). `contattato_at` si marca alla
  prima volta e non si sposta più.
- `POST /leads/<id>/prendi/` — presa in carico. Assegna **sempre** a chi
  chiama; **409** se è già di un altro, col nome. È il conflitto che la pagina
  serve a evitare: due messaggi alla stessa persona.
- `POST /leads/<id>/rilascia/` — solo chi l'ha preso (o superuser).
- `GET /leads/riepilogo/` — conteggi per stato e gruppi presenti.
- `POST /leads/chiudi-campagna/` — **`IsPropertyProprietario`**, non membro
  qualsiasi: cancellare butta via anche le note e la presa in carico degli
  altri, e l'utente del bot ha la password in chiaro nel TOML. Vedi sotto.

L'utente del bot dev'essere **membro dell'immobile** (`PropertyMembership`), non
solo del gruppo `proprietari`: senza, ogni giro prende 403 e la coda si ferma
in silenzio fino all'avviso dei dieci lead fermi.

L'upsert valida **riga per riga**: una riga malformata viene scartata e
segnalata in `scartati`, le altre passano. Rifiutare l'intero blocco fermerebbe
per sempre la coda del bot, che ritenta sempre lo stesso blocco.

# Push dal bot: best-effort, mai bloccante

Telegram resta il canale primario. Il push su viapal non deve poter fermare il
giro del bot né far perdere un contatto:

- coda = colonna `pushed_at` NULL nel SQLite del bot; si ritenta a ogni giro e
  l'endpoint idempotente rende il ritenta gratuito;
- il server può stare spento un giorno intero senza perdite;
- avviso su Telegram solo oltre i 10 lead fermi (sotto è un buco di rete);
- vanno solo i **match**, non gli scarti: la pagina serve a contattare, non a
  rivedere il classificatore — e meno dati di terzi arrivano sul server, meglio è;
- niente sezione `[api]` nella config del bot = push spento, comportamento di
  prima.

# Chiusura di campagna

`POST /leads/chiudi-campagna/` con `{"conferma": true}` cancella i lead
dell'immobile attivo (dal menu ⋮ della pagina). È speculare alla cancellazione
del `.db` sul portatile del bot: la spec del bot dice «a campagna chiusa si
cancella il database, punto», e il principio deve valere anche per la copia sul
server, che ospita nomi, profili e testi di terze persone. Vedi il piano
privacy in `docs/privacy/`.

# La pagina

`/p/cerca-inquilini`, sezione Inquilini del menu — l'etichetta è **"Cerca
inquilini"**: "lead" non è una parola di casa. Mobile-first, perché si usa dal
telefono con Messenger accanto.

Card per contatto: in testa **stato** (badge + fondo colorato: "Da
contattare" resta senza colore di proposito, scartato è smorzato e barrato) e
**chi ci sta scrivendo** (badge col nome, o "lo contatti tu"), fotina accanto
al nome; poi fatti in una riga (zona, budget, da quando, stanze
compatibili), motivo del classificatore, post accorciato ed espandibile, quattro
azioni (**Messenger**, **il post**, **copia commento**, **copia privato** — i
due tasti di copia sostituiscono il tap-che-copia di Telegram), la nota come
foglietto leggibile nella card (non solo tooltip: su telefono l'hover non
esiste) e in fondo presa in carico, stato e note. Colori e icone degli stati
stanno in `STATI` (store `leads.ts`), condivisi da filtri, select e card.
Ctrl-Invio salva la nota dal dialog. Con un filtro attivo il lead che cambia
stato sparisce dall'elenco: una notifica dice dov'è finito e offre di andarci.

Il gruppo si mostra solo se i gruppi presenti sono più d'uno.

# Sviluppo

`manage.py seed_leads --property <id>` crea quattro lead finti (`--pulisci` li
toglie): la pagina si sviluppa senza far girare uno scrape vero di Facebook a
ogni ritocco.
