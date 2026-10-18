---
type: Playbook
title: Dev setup
description: Avviare backend e frontend in locale (senza Docker).
resource: justfile
resources:
  - justfile
  - backend/core/settings/dev.py
  - frontend/quasar.config.ts
  - backend/apps/properties/management/commands/seed_demo.py
  - backend/core/settings/demo.py
  - backend/core/settings/__init__.py
  - backend/apps/properties/management/commands/cura_demo_video.py
  - backend/apps/properties/management/commands/anonimizza_demo.py
  - backend/apps/properties/management/commands/copia_media_demo.py
  - backend/apps/properties/anonimizza_demo.py
  - backend/apps/properties/test_anonimizza_demo.py
tags: [playbook, dev, setup]
generated:
  by: process:okf-migrate
  at: 2026-10-18T12:00:00Z
---

# Prerequisiti

`uv` ≥ 0.8, `bun` ≥ 1.2, `node` ≥ 22.22, `just`, `agent-browser` (validazione
visuale). Postgres: cluster `dev` su porta 5434, db `viapal`, utente `sandro`
(peer auth via socket). In dev **niente Docker**.

# Avvio

```bash
# Backend
cd backend && uv sync
ENV=dev uv run python manage.py migrate
# Dati e utenti demo (il migrate crea solo i gruppi)
ENV=dev uv run python manage.py seed_demo   # --reset azzera le app di dominio
# Frontend
cd ../frontend && bun install
# Tutto in parallelo
cd .. && just up
```

- Backend admin: <http://localhost:8020/admin/> (`admin` / `admin`)
- Frontend: <http://localhost:9020/login> (host alternativi in
  `quasar.config.ts: allowedHosts` + `settings/dev.py: _ORIGINI_DEV`:
  `viapal.local:9020` e `viapal.localhost:9020`)
  - Per le **notifiche push** serve un contesto sicuro: usare
    `viapal.localhost` (o `localhost` nudo), mai `viapal.local`, che essendo
    http su nome non speciale spegne `serviceWorker`/`PushManager`.
  - `viapal.localhost` va messo in `/etc/hosts` puntato a `127.0.0.1`: il
    resolver di sistema lo risolve a `::1`, ma i dev server ascoltano su IPv4.
- I superuser hanno i link "→ App Viapal" (admin) e "Admin Django" (drawer
  proprietario); il primo passa da `APP_BASE_URL`, perché in dev le due
  porte sono diverse.

# Porte e worktree paralleli

- `VIAPAL_BACKEND_PORT` sposta il target del proxy Quasar (default 8020),
  `VIAPAL_FRONTEND_PORT` sposta la porta del dev server Quasar e aggiunge
  un'origine CSRF/CORS fidata (default 9020, anche 9200): un secondo
  worktree parte senza toccare i file.
- `VIAPAL_DB_NAME` sceglie un database (e quindi un test DB) distinto per
  pytest in parallelo.
- Il dev server Quasar proxa `/api`, `/admin`, `/static`, `/media-private`,
  `/media` e `/g/` verso Django.

# Utenti dev (creati da `seed_demo`, non dal migrate)

| Username | Password | Ruolo |
|---|---|---|
| `admin` | `admin` | superuser |
| `sandro` / `bruna` / `fabio` | `<username>pwd` | proprietari |
| `mariasevera` / `davide` / `diana` / `arun` / `eshani` | `<username>pwd` | inquilini |

# Comandi just

`just backend` · `just frontend` · `just up` · `just migrate` · `just test` ·
`just lint` · `just build`.

# Email in dev (MailHog)

SMTP catcher Docker su `:1025` (SMTP) e `:8025` (UI), configurato in `local.py`;
`just mailhog` / `just mailhog-stop` lo avviano e fermano (container
`viapal-mailhog`, auth-file in `~/.config/mailhog/auth.txt`).

# Media di produzione in locale

`jmb.core` `FallbackStorage`, configurato in `local.py` (`MEDIA_FALLBACK_S3_*`):
legge prima dal filesystem locale e, se il file manca, dal proxy S3 read-only
di prod. Spento sotto pytest. Non richiede di copiare la `media/`.

# Ambiente demo (riprese video)

`just demo` avvia backend `:8022` e frontend `:9022` con `ENV=demo`
(`settings/demo.py`): db fisso `viapal_demo` (copia **anonimizzata** della
produzione, non toccata da `jmb-sync`), media in `media-demo/` e
`media-private-demo/`, email sulla console. Con `ENV=demo` `local.py` **non
viene letto** (`settings/__init__.py`): così il `FallbackStorage` verso S3 di
produzione non può servire documenti veri dietro ai nomi finti.

Il video demo si gira e si monta da `video/` (vedi `video/STORYBOARD.md`;
lanciare prima `cura_demo_video`, vedi sotto):
`video/riprese/scene/NN-*.sh` registrano le clip (Chrome headless pilotato da
agent-browser, screencast CDP a 30 fps; `bash video/riprese/lib.sh -h`),
`video/src/manifest.ts` le taglia e mette le didascalie, `npm run render`
produce `video/out/viapal-demo.mp4`. Clip e render non sono versionati.

## Ricetta di ricostruzione (da zero)

```bash
jmb-sync                                   # aggiorna il db `viapal` dalla produzione
dropdb -p 5434 viapal_demo && createdb -p 5434 -T viapal viapal_demo
                                           # -T fallisce se ci sono connessioni a `viapal`
cd backend && rm -rf media-private-demo
ENV=demo uv run python manage.py migrate
ENV=demo uv run python manage.py anonimizza_demo --dry-run   # report + rollback
ENV=demo uv run python manage.py anonimizza_demo             # per davvero
ENV=dev VIAPAL_DB_NAME=viapal_demo uv run python manage.py copia_media_demo
ENV=demo uv run python manage.py cura_demo_video            # ritocchi per le riprese
```

* `cura_demo_video` (idempotente) toglie le code della storia vera che in un
  video stonano: arretrati degli ex inquilini (la pagina Notifiche addebiti
  conta tutti gli addebiti "da pagare", `insoluto` compreso, di chi non ha
  un'assegnazione in corso; senza allocazioni si eliminano, con allocazioni
  il dovuto scende all'incassato e diventano pagati col proprietario
  incassante), documenti generati (atti/cessioni) di Miriam Tosi (il dialog
  "Genera" resta pulito), addebiti storici residui → `insoluto`, membership
  del `bot`, notifiche push fallite. Aggiunge anche l'unico addebito
  "in attesa di conferma" del db: l'ultimo aperto di Luigi Cirillo (Casa dei
  Tigli, Utenze Ago 2026, 39,26 €) passa a `dichiarato` con
  `billing.calc.incassi.dichiara_pagamento`, lo stesso servizio
  dell'endpoint `dichiara_pagato`, ma **senza** l'avviso push ai proprietari
  che l'endpoint manda dopo. Serve alla scena 07 "Notifiche" (nei ritardi
  compare "Da confermare"); Diego Palmieri, protagonista delle scene 02–06,
  resta com'era. Le costanti `USERNAME_RIPRESE` e `INQUILINO_DICHIARANTE`
  usano i nomi finti: se l'anonimizzazione cambia, vanno aggiornate.

* `anonimizza_demo` gira solo su `viapal_demo` con `ENV=demo` e **una volta
  sola** per db: gli importi vengono scalati (x 0,7) e la tabella
  `demo_anonimizzazione` (SQL grezzo, nessuna migrazione) rifiuta il secondo
  giro. Una sola transazione; se la verifica finale trova dati reali residui
  (token reali in qualsiasi colonna testuale, email/IBAN/CF/telefoni/P.IVA non
  finti) fallisce e fa rollback (`--ignora-residui` per scavalcare).
* `--campioni FILE` scrive le parole "non italiane" rimaste nei testi e
  un dump leggibile delle tabelle anagrafiche: serve a cercare **a occhio** i
  nomi di terzi sfuggiti. Il dizionario conosce solo ciò che è in anagrafica
  (utenti, profili, luoghi, vie); chi paga un bonifico o compare in una nota
  senza avere un profilo va nell'elenco locale `~/.config/viapal-demo/nomi-terzi.txt`
  (un nome per riga, **fuori dal repo**, opzione `--nomi-terzi`). Dopo ogni
  `jmb-sync` conviene un giro di `--dry-run --campioni` per vedere se sono
  comparsi nomi nuovi.
* `copia_media_demo` copia in `backend/media-demo/` le sole foto vere
  (galleria, stanze, immobile: `Property.foto_hero/planimetria/mappa`,
  `GalleryImage.image`, `Room.foto`) dallo storage di dev (che legge da S3 di
  produzione). Tutti gli altri file (documenti identità, bollette, allegati,
  documenti generati) sono sostituiti da PDF/immagini segnaposto "Documento di
  esempio - dati fittizi" in `media-private-demo/`, con i percorsi riscritti
  col nome finto (es. `documenti/70-miriam/`).

## Cosa viene trasformato

Mappatura deterministica (seed fisso: due giri su un db fresco danno gli
stessi nomi). Persone: nomi/cognomi (anche su `User.first_name/last_name`, che
la home inquilino usa per il saluto; chi aveva solo il nome riceve un cognome
finto), username (nome finto in minuscolo),
email `nome.cognome@example.com`, telefoni, codici fiscali e IBAN con
checksum valido (ABI `99999`, non assegnato: il QR di pagamento non può
puntare a un conto vero; banche con nomi fittizi), date di nascita (spostate), luoghi di nascita e residenza,
documenti. Gli inquilini diventano tutti **italiani tranne uno**
(`INQUILINO_STRANIERO_USER_ID`, oggi Tarek Saleh, egiziano: ex inquilino
giugno–settembre 2026, visibile solo nella ripartizione utenze di luglio; gli
inquilini attivi sono tutti protagonisti delle scene): nomi per generazione
(l'anno di nascita viene dal codice fiscale vero, spostato di qualche mese),
cognomi e luoghi di nascita da tutta Italia, cittadinanza e codice fiscale
coerenti; il permesso di soggiorno di un italiano diventa carta d'identità e il
passaporto lo rilascia la Questura. I loro pool (`NOMI_INQUILINI`,
`COGNOMI_INQUILINI`, `COMUNI_NASCITA_INQUILINI`) sono disgiunti da quelli di
proprietari, lead e terzi, che restano come prima: un inquilino non può avere
il cognome di un proprietario. Fra i proprietari gli stranieri restano
stranieri (nomi coerenti con cittadinanza e luogo di nascita), i fratelli
proprietari condividono il cognome. Immobili: Novara, "Via dei Tigli", CAP 28100, nomi
"Casa dei Tigli" / "Casa dei Gelsomini" (Galliate), testi della galleria
riscritti. Testo libero di ogni modello (movimenti bancari, note, notifiche,
modelli di documento) passato dal dizionario con confini di parola; lead del
bot Facebook rigenerati da template (autori, post, URL, fotina azzerata).
Cancellati: sessioni, log admin, push, token, conferme email. Il nome del
prodotto "Viapal" resta.

Ritocchi di presentazione (tutti in `anonimizza_demo`): telefoni finti
`333 000 NNNN`; alias di stanza "mamma"/"papà" → "Camera 2"/"Camera 3" e
pratiche di successione → "imposta" (`FRASI_NEUTRE`, anche nei percorsi file);
note lunghe o che citano i fogli storici → "Nota di archivio."; descrizioni dei
movimenti fra proprietari sostituite da etichette neutre ("Bonifico fra
proprietari (luglio 2024)"); numeri di bolletta rigenerati (11 cifre) con
nomi file `bollette/<slug>/<anno>/<mese>/<prodotto>-<numero>.pdf`; gruppi dei
lead con un nome finto sempre valorizzato e coppie nome/cognome della stessa
provenienza; titolo galleria = nome della casa. La verifica residui fallisce
anche se restano parole di parentela/successione, "monza" o "-mz-".
I segnaposto immagine usano solo ASCII (il font di PIL non ha gli accenti).

Importi x 0,7 (arrotondamento al centesimo, mezzo in su) su tutti i
`DecimalField` tranne `OwnershipShare.quota`, `Room.superficie_mq`,
`UtilityBill.consumo`; stessa scalatura per gli importi scritti accanto a "€"
nei testi. Gli invarianti sono riparati al centesimo: un movimento saldato
resta pari alla somma delle sue allocazioni, un addebito saldato pari alle
sue, i parziali restano parziali (stessa classe rispetto alla tolleranza di
1 euro / 0,01), il deposito versato resta pari ai versamenti, il costo
cessione pari al doppio della quota inquilino. Il comando stampa conteggi
prima/dopo (identici o fallisce) e le somme per campo (~0,7x).

Limite noto: le cifre scritte nella causale bancaria *senza* simbolo
(`FITTO 450+70`) restano quelle originali.

## Login nell'ambiente demo

Password di **tutti** gli utenti: `demo2026`.

| Username | Ruolo |
|---|---|
| `admin` | superuser (admin Django) |
| `massimo` | proprietario principale: proprietario di Casa dei Tigli, gestore di Casa dei Gelsomini |
| `irene`, `ettore` | proprietari di Casa dei Tigli |
| `greta` | proprietario di Casa dei Gelsomini |
| `diego` | inquilino attivo, Camera 4 (Diego Palmieri: scene 02–06, home inquilino) |
| `luigi` | inquilino attivo, Camera 3 (Luigi Cirillo: addebito "dichiarato" della scena 07) |
| `miriam` | inquilina attiva, subentrata in Camera 1 (Miriam Tosi: scena 11, ha pagamenti dichiarati) |
| `christian` | inquilino di Casa dei Gelsomini (Christian Brambilla: scene 05 e 12) |
| `tarek` | ex inquilino, l'unico straniero (Tarek Saleh) |
| `erica`, `sergio`, `ilenia`, `rossella`, `ciro`, `claudia`, `mirko`, `angela`, `barbara`, `marta`, `raffaella`, `concetta` | ex inquilini |
| `storico_emiliano`, `storico_antonino`, `storico_annalisa`, `storico_gianluca` | inquilini storici (solo anagrafica) |
| `brambilla-christian` | duplicato di `christian` (stessa persona, secondo utente) |
| `bot` | tecnico (membership del bot dei lead) |

# Vedi anche

- [Architecture overview](/architecture/overview.md), [Validazione](/playbooks/validazione.md).
