# Accordo per il trattamento di dati personali (art. 28 GDPR)

*Da far firmare a ogni proprietario accreditato sulla piattaforma.
Due copie firmate (anche scambio via e-mail con firma scansionata è
sufficiente); conservare per tutta la durata del rapporto e 5 anni oltre.*

---

**Tra**

**{{nome_proprietario}}**, C.F. {{cf_proprietario}}, residente in
{{indirizzo_proprietario}}, e-mail {{email_proprietario}}, in qualità di
locatore degli immobili gestiti tramite la piattaforma (di seguito il
**Titolare**),

**e**

**Sandro Dentella**, C.F. {{cf_sandro}}, residente in {{indirizzo_sandro}},
e-mail sandro.dentella@gmail.com, in qualità di gestore della piattaforma
software "Viapal" (di seguito il **Responsabile**),

si conviene quanto segue.

## 1. Oggetto e durata

1.1 Il Responsabile mette a disposizione del Titolare, **a titolo
gratuito**, la piattaforma Viapal per la gestione delle locazioni
(anagrafiche inquilini, documenti, canoni, pagamenti, utenze, comunicazioni)
e tratta per conto del Titolare i dati personali descritti nell'**Allegato
A**, esclusivamente per l'erogazione del servizio.

1.2 L'accordo ha la durata del rapporto di utilizzo della piattaforma e
cessa con la chiusura dell'account del Titolare, fatti salvi gli obblighi di
cui all'art. 8.

## 2. Istruzioni del Titolare

Il Responsabile tratta i dati soltanto su istruzione documentata del
Titolare. Le funzionalità della piattaforma e il presente accordo
costituiscono le istruzioni iniziali; istruzioni ulteriori vanno impartite
per iscritto (anche via e-mail). Il Responsabile informa il Titolare qualora
ritenga che un'istruzione violi la normativa sulla protezione dei dati.

## 3. Riservatezza

Il Responsabile garantisce che le persone autorizzate ad accedere ai dati
(attualmente il solo Responsabile) si sono impegnate alla riservatezza.
L'accesso del Responsabile ai dati del Titolare è limitato a quanto
necessario per manutenzione, assistenza e sicurezza della piattaforma.

## 4. Misure di sicurezza

Il Responsabile adotta le misure tecniche e organizzative descritte
nell'**Allegato B**, adeguate al rischio ai sensi dell'art. 32 GDPR.

## 5. Sub-responsabili

5.1 Il Titolare autorizza in via generale il ricorso ai sub-responsabili
elencati nell'**Allegato C**.

5.2 Il Responsabile comunica al Titolare ogni modifica prevista (aggiunta o
sostituzione); il Titolare può opporsi entro 15 giorni; in caso di
opposizione, il Titolare può recedere dal servizio.

5.3 Il Responsabile impone a ciascun sub-responsabile, mediante contratto,
obblighi equivalenti a quelli del presente accordo.

## 6. Assistenza al Titolare

Il Responsabile assiste il Titolare, tenuto conto della natura del
trattamento:

- nel dare seguito alle richieste di esercizio dei diritti degli interessati
  (artt. 15–22 GDPR), anche tramite le funzionalità self-service della
  piattaforma;
- negli obblighi di cui agli artt. 32–36 GDPR (sicurezza, notifica delle
  violazioni, valutazioni d'impatto).

## 7. Violazioni di dati personali

Il Responsabile informa il Titolare **senza ingiustificato ritardo, e
comunque entro 48 ore** dal momento in cui ne è venuto a conoscenza, di ogni
violazione di dati personali che riguardi i dati trattati per conto del
Titolare, fornendo le informazioni utili alla eventuale notifica al Garante
(art. 33 GDPR).

## 8. Cessazione: restituzione e cancellazione

Alla cessazione del servizio il Responsabile, a scelta del Titolare:
(a) restituisce i dati in formato strutturato di uso comune (export), e/o
(b) cancella i dati e le copie esistenti entro 60 giorni, salvo obblighi di
conservazione previsti dalla legge. I dati presenti nei backup vengono
sovrascritti secondo il normale ciclo di rotazione (max {{giorni_backup}}
giorni).

## 9. Audit

Il Responsabile mette a disposizione le informazioni necessarie a dimostrare
il rispetto del presente accordo e consente verifiche da parte del Titolare,
previo preavviso ragionevole e con modalità che non compromettano la
sicurezza degli altri utenti della piattaforma.

## 10. Responsabilità del Titolare

Resta a carico del Titolare, quale titolare del trattamento: la liceità dei
dati caricati, il rilascio dell'informativa ai propri inquilini (la
piattaforma fornisce un modello), la correttezza delle basi giuridiche e la
gestione dei rapporti con gli interessati.

---

Luogo e data: ______________________

Il Titolare: ______________________

Il Responsabile: ______________________

---

## Allegato A — Dettagli del trattamento

- **Natura e finalità**: hosting e gestione applicativa dei dati per
  l'amministrazione di locazioni (contratti, canoni, pagamenti,
  riconciliazione bancaria, utenze, documenti, comunicazioni agli
  inquilini).
- **Categorie di interessati**: inquilini e loro eventuali garanti;
  comproprietari; contatti amministrativi.
- **Categorie di dati**: anagrafici e di contatto; codice fiscale; copie di
  documenti d'identità e permessi di soggiorno; documentazione reddituale;
  dati contrattuali e contabili (canoni, bonifici, IBAN, depositi);
  credenziali di accesso; log tecnici.
- **Durata**: per la durata dell'account del Titolare (v. art. 8).

## Allegato B — Misure di sicurezza

- Cifratura del canale (HTTPS/TLS) per ogni accesso all'applicazione.
- Autenticazione individuale; i documenti sono accessibili solo agli utenti
  autorizzati (l'interessato e il rispettivo locatore); serving dei file
  soggetto a controllo di autorizzazione applicativo (nessun URL pubblico).
- Separazione dei dati tra proprietari (autorizzazioni per membership).
- Accessi amministrativi limitati al Responsabile, protetti da credenziali
  robuste; accesso "impersonate" tracciato.
- Server ubicati nell'Unione Europea (Contabo GmbH, Germania); sistema
  operativo e componenti aggiornati.
- Backup periodici cifrati/protetti, con rotazione max {{giorni_backup}}
  giorni; ripristino testato.
- Registro delle violazioni e procedura di gestione dei data breach.

## Allegato C — Sub-responsabili autorizzati

| Sub-responsabile | Sede | Attività | Garanzie |
|---|---|---|---|
| Contabo GmbH | Monaco di Baviera, Germania (UE) | Hosting (VPS) | DPA art. 28 concluso tramite Customer Control Panel |
| {{fornitore_smtp}} | {{sede_smtp}} | Invio e-mail transazionali | {{dpa_smtp}} |
