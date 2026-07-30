# Piano di adeguamento GDPR — Viapal

Contesto: locazione di stanze gestita da privati (Sandro + fratelli) tramite
piattaforma propria; primo proprietario esterno accreditato: la moglie di
Sandro. Nessun allargamento previsto. Hosting: VPS Contabo GmbH (Germania,
UE). Documenti d'identità degli inquilini caricati direttamente in app
(`TenantDocument`).

## Esito verifica media (2026-07-30) — CRITICO

**Oggi i documenti d'identità sono scaricabili senza autenticazione da
chiunque conosca (o indovini) l'URL**, sia in dev sia in produzione:

- In produzione uwsgi serve i media come statici, senza alcun controllo:
  `static-map = /media=/code/media` (`backend/uwsgi.ini:32`); Traefik
  instrada `/media` direttamente al container Django
  (`docker-compose.yml:44`).
- In dev fa lo stesso `static(settings.MEDIA_URL, ...)`
  (`backend/core/urls.py:36`).
- I percorsi sono **indovinabili**: `documenti/<tenant_id>-<slug
  nominativo>/<filename>` (`backend/apps/properties/models/tenant.py:151`);
  idem `bollette/<immobile>/<anno>/<mese>`, `ricevute/`, `spese/`.
- I serializer espongono l'URL diretto (`backend/apps/properties/serializers.py:397`)
  e il frontend linka `doc.file` così com'è
  (`frontend/src/components/DocumentiPannello.vue:132`).

Unica eccezione voluta: le immagini della galleria pubblica (`galleria/`,
`rooms/`) devono restare accessibili senza login (annuncio `/g/<slug>`).

## Fase 0 — Media protetti (da fare SUBITO, prima di ogni altra cosa)

1. **Vista di download autenticata** su `/media/<path>` (Django,
   `FileResponse`): con ~8 utenti non servono X-Accel/offload.
   Matrice di autorizzazione per prefisso:
   - `documenti/<tenant_id>-…` → l'inquilino stesso, oppure un utente con
     membership sulla proprietà dell'inquilino, oppure superuser;
   - `documenti-casa/` (PropertyDocument) → membri della proprietà; se
     `visibile_inquilini`, anche gli inquilini della proprietà;
   - `bollette/`, `ricevute/`, `spese/` → membri della proprietà; bollette e
     ricevute anche agli inquilini interessati (le vedono già in
     `/i/utenze`);
   - `galleria/`, `rooms/` → pubblico (AllowAny);
   - default per prefissi ignoti → negato (fail-safe).
2. **Togliere `static-map = /media`** da `uwsgi.ini` così le richieste
   arrivano alla vista; in dev sostituire `static()` con la stessa vista
   (comportamento identico dev/prod).
3. Verificare che il download via `href` funzioni con l'autenticazione di
   sessione (cookie): se il FE usasse token nell'header, i link diretti non
   sarebbero autenticati e servirebbe un adattamento.
4. Test: matrice permessi (anonimo/inquilino/altro inquilino/proprietario/
   altra proprietà/superuser) + galleria pubblica ancora accessibile.
5. Validazione con agent-browser: da anonimo, URL diretto di un documento →
   403/302; da inquilino → scarica il proprio, non quello altrui.
6. (Consigliato) log degli accessi ai documenti (chi, cosa, quando) — utile
   anche come misura dimostrabile art. 32.

## Fase 1 — Adempimenti documentali (uso in proprio)

1. **Informativa inquilini** (`informativa-inquilini.md`): compilare i
   placeholder e mostrarla in app — link in `/i/documenti` accanto
   all'upload e nel profilo. Niente checkbox di consenso: le basi sono
   contratto/obbligo legale, basta che sia visibile.
2. **Retention**: adottare le regole scritte nell'informativa. Minimo: un
   management command di report (`documenti_scaduti`) che segnali i
   contratti di lavoro più vecchi di 12 mesi dalla firma e i documenti di
   inquilini usciti da oltre 5 anni; la cancellazione resta manuale e
   consapevole.
3. **Registro dei trattamenti** (`registro-trattamenti.md`): compilare
   sezione A e tabella fornitori. 30 minuti.
4. **Procedura breach** (`procedura-data-breach.md`): già pronta, basta
   saperla ritrovare.
5. **Contabo**: concludere il DPA standard dal Customer Control Panel
   (procedura self-service prevista da Contabo, nessuna lettera da
   scrivere). Archiviare il PDF e annotare la data nel registro.
   Rif: help.contabo.com, articolo 103000274684.
6. **SMTP di produzione**: quando verrà scelto il provider e-mail reale,
   aggiungerlo come sub-responsabile (registro + Allegato C dell'accordo) e
   verificare che abbia sede/server UE o garanzie di trasferimento.
7. **Backup**: verificare che i backup di `./data/media` e del DB su host
   siano protetti (cifratura o quantomeno accesso ristretto) e annotare la
   rotazione nel placeholder `{{giorni_backup}}` dell'accordo.

## Fase 2 — Accreditamento della moglie (e futuri proprietari)

Per ogni proprietario esterno, PRIMA di dare accesso:

1. Far firmare **accordo art. 28** (`accordo-responsabile-art28.md`) +
   **condizioni d'uso e informativa proprietari**
   (`condizioni-uso-e-privacy-proprietari.md`). Anche via e-mail con
   scansione firmata; archiviare.
2. Aggiungere la riga nella **sezione B del registro**.
3. Ricordarle che per i **suoi** inquilini è lei il titolare: deve usare
   l'informativa (template con i placeholder risolti sui suoi dati) — la
   Fase 0/1 fa sì che l'app gliela mostri già giusta se i dati della
   proprietà sono compilati.
4. Verificare l'**isolamento**: con il suo account non deve vedere nulla
   delle proprietà dei fratelli (membership già in piedi dal lavoro
   multiproprietà; la vista media di Fase 0 deve applicare lo stesso
   confine). Nota: il bypass superuser esistente è accettabile finché il
   superuser è solo Sandro (che è comunque responsabile ex art. 28), ma gli
   accessi ai dati di altri titolari vanno limitati al necessario.

## Cosa NON serve (a questa scala)

- DPO, DPIA formale, rappresentante UE.
- Consensi: le basi giuridiche corrette sono contratto e obbligo legale
  (consenso solo per le notifiche push, già opt-in).
- Contratti con Agenzia Entrate/autorità PS: sono titolari autonomi.

## Deploy in produzione (Fase 0)

La feature richiede, al primo deploy, uno spostamento dei file sul server:

1. pull/build della nuova immagine e `docker compose up -d` (il compose ora
   monta anche `./data/media-private:/code/media-private`);
2. nel container: `python manage.py migra_media_private --dry-run` e poi
   senza `--dry-run` (sposta documenti/bollette/ricevute/spese da
   `data/media` a `data/media-private`);
3. verifica: URL `/media-private/...` da anonimo → 403; vecchio URL
   `/media/documenti/...` → 404; foto galleria pubblica → 200.

Nota tecnica: in `uwsgi.ini` lo static-map è `/media/=/code/media/` con
trailing slash obbligatorio (altrimenti il match per prefisso servirebbe
anche `/media-private` come statico, bypassando la vista).

## Stato

- [x] Fase 0.1–0.5 media protetti (vista `core/media_private.py`, test
      `test_media_private.py`, validato in dev con agent-browser 2026-07-30)
- [x] Fase 0.6 log accessi documenti (logger `viapal.media_private`)
- [x] Fase 0 deploy in produzione (2026-07-30: immagini via CI, compose
      aggiornato su mio3, `migra_media_private` → 66 file, verifiche
      esterne: doc 403 da anonimo, vecchi URL 404, galleria 200)
- [x] Fase 1.1 informativa in app (`/i/privacy` + endpoint
      `/api/v1/privacy/informativa/`; placeholder gestore nei settings)
- [x] Fase 1.2 command retention (`documenti_scaduti`, solo report)
- [ ] Fase 1.3 registro compilato
- [x] Fase 1.5 DPA Contabo concluso (2026-07-30, dal Customer Control
      Panel; annotare gli estremi nel registro)
- [ ] Fase 1.7 verifica backup
- [ ] Fase 2 firma documenti moglie + riga registro
