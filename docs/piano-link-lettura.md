# Piano: link di lettura dei documenti (pagina pubblica a token)

> Stato al 2026-08-26: **fasi 1–3 implementate** (backend, FE gestione, pagina
> pubblica). Restano la **fase 4** (variante anonima dell'atto di subentro) e
> la **fase 5** (caricare le copie oscurate vere e comporre il primo
> pacchetto), che dipende da file che l'applicazione non produce.
>
> Due scostamenti dal piano, decisi in corso d'opera:
> - **`copia_di` è `PROTECT`, non `SET_NULL`** — vedi Parte 3, nota in fondo;
> - **l'anteprima del markdown passa da un endpoint**, non da un renderer JS
>   nel browser: due renderer significherebbero un'anteprima che mente;
> - **tre dei quattro filtri di lista sono client-side** — vedi la nota
>   sotto la tabella nella Parte 4.

Mandare a un inquilino in arrivo un link, senza account, che apra i documenti
da leggere prima della firma, **senza i dati personali di chi ha firmato prima**.

Scelte già prese: link a solo token, senza scadenza, revocabile; **la copia
oscurata si carica una volta sola e si riusa**; i file oscurati li prepara e
carica Sandro — l'applicazione non entra nel merito dell'oscuramento;
**l'atto di subentro entra nel pacchetto in versione anonima**, come anteprima
di cosa si firmerà.

---

# Parte 1 — Cosa si vede e cosa si fa

## Le copie per la lettura: caricate una volta

Nel tab «Contratti e documenti», sul chip di un documento del contratto (o
sulla riga di uno della casa) compare una nuova azione: **«Copia per la
lettura»**. Chiede il PDF oscurato e lo aggancia all'originale.

Da lì in poi quella copia vive in una sezione sua:

```
Copie per la lettura                     [ + Copia per la lettura ]
──────────────────────────────────────────────────────────────────
  📄 Contratto di locazione — copia oscurata           in 2 link  ✎ 🗑
     copia di: Contratto 2025 firmato · Collettivo 2025
  📄 Lettera di accompagnamento — copia oscurata       in 2 link  ✎ 🗑
     copia di: lettera accompagnamento · Collettivo 2025
```

**Non compare** nei chip del contratto, né in «Altri documenti», né nella
pagina degli inquilini: l'archivio ufficiale resta quello che è. Il legame
con l'originale è esplicito, quindi si sa sempre di che cosa è copia.

Le regole di convivenza non hanno bisogno di copia — non nominano nessuno:
restano dove sono, con una spunta **«esponibile»** sulla riga.

Nel dialog di caricamento, due righe di avvertenza — non in un documento che
nessuno rilegge, ma dove si carica il file:

> Il rettangolo nero disegnato sopra un testo **non lo cancella**: resta
> sotto e si recupera con un copia-incolla. Copri, poi appiattisci il PDF in
> immagini. Controlla anche i metadati (autore, titolo).

Vale per il contratto 2025, che è un PDF misto: la prima pagina ha testo
vero (nome, luogo di nascita e codice fiscale si estraggono con `pdftotext`),
le altre sei sono scansioni JPEG.

## I link

Terza sezione, **«Link di lettura»**:

```
Link di lettura                                    [ + Nuovo link ]
──────────────────────────────────────────────────────────────────
  Per Oussama Bouchane            aperto 3 volte · l'ultima il 22/07
  viapal.it/d/kR7f…                    [copia link] [modifica] [revoca]

  Per Simona Bagnato              mai aperto
  viapal.it/d/9Twx…                    [copia link] [modifica] [revoca]
```

Il compositore mette in fila voci di due forme — un documento esponibile,
oppure un testo scritto da te:

```
Pacchetto per: [Simona Bagnato          ]

 ☰ 1. 📄 Contratto di locazione — copia oscurata                      ✎ 🗑
 ☰ 2. 📄 Lettera di accompagnamento — copia oscurata                  ✎ 🗑
 ☰ 3. 📝 Cosa pagherai ogni mese                       (chiarimento)  ✎ 🗑
 ☰ 4. 📄 Atto di subentro (anteprima anonima)                         ✎ 🗑
 ☰ 5. 📄 Regole di convivenza                                         ✎ 🗑

   [ + Aggiungi documento ]  [ + Genera anteprima ]  [ + Scrivi un testo ]
```

«Aggiungi documento» propone **solo** ciò che è esponibile: le copie per la
lettura e i documenti spuntati. L'originale non è nell'elenco, quindi non c'è
nessun modo di sceglierlo per sbaglio.

Per il secondo inquilino rifai il pacchetto in quattro click: i file sono già
lì, non si ricarica niente.

## Il nuovo inquilino

Apre il link e trova una pagina sola: il nome della casa, il suo nome, le voci
nell'ordine che hai dato. I PDF si aprono lì dentro, i chiarimenti stanno come
testo formattato in mezzo agli allegati.

---

# Parte 2 — Perché così

## Il pacchetto referenzia, non copia

Il documento è sempre lo stesso: caricarlo per ogni inquilino sarebbe lavoro
inutile e file duplicati. Quindi la voce del pacchetto **punta** al documento
esponibile.

Rovescio della medaglia, da sapere: se sostituisci il file di una copia
esponibile, cambia anche per i link già mandati. Per «il contratto oscurato,
sempre uguale» è quello che vuoi — se correggi un'omissione la correggi
ovunque. Se un giorno servisse congelare un pacchetto, si aggiunge allora.

## Due campi, due significati distinti

Su `PropertyDocument`:

- **`copia_di`** (FK a sé stesso, nullable) — «questo non è un originale, è la
  copia per la lettura di quell'altro». Valorizzato ⇒ fuori da tutte le liste
  ufficiali, dentro «Copie per la lettura». È la risposta alla tua obiezione:
  la copia non sporca i documenti del contratto.
- **`esponibile`** (bool, default False) — «può stare in un link». Serve alle
  regole di convivenza, che sono un documento ufficiale a tutti gli effetti e
  vanno esposte così come sono. Una copia per la lettura nasce con la spunta
  già messa: è il suo unico scopo.

Tenerli separati evita il pasticcio del flag unico: «non è ufficiale» e «si
può mandare fuori» sono cose diverse, e un documento può essere la seconda
senza essere la prima.

**Invariante**: nel link entra solo ciò che è `esponibile`, e il controllo è
al **momento del serving**, non solo quando componi. Togli la spunta e i link
già mandati smettono di servire quel file — è la revoca a grana fine.
Una copia non può avere copie: un livello solo.

Non chiamo il campo «modello» o «template» perché in questa stessa pagina
c'è già la sezione «Modelli dei documenti generati» (`DocumentTemplate`, il
testo dell'atto di subentro): due cose diverse con lo stesso nome a due
centimetri di distanza. «Copia per la lettura» dice cos'è. Se preferisci
un'altra parola è una stringa da cambiare.

## Il testo di chiarimento

La seconda forma di una voce: titolo + corpo in **markdown** (grassetto,
elenchi, titoli, tabelline), con anteprima mentre scrivi. Ci metti la quota
condominio in vigore, come funzionano le utenze, quando si paga.

Reso in HTML **lato backend**, sanitizzato con allowlist stretta (`nh3`) e
salvato accanto al markdown: la pagina pubblica mostra solo HTML già passato
dal sanitizzatore. Il progetto ha già la regola per l'HTML scritto da un
utente — `ComunicazioniPannello` mette il corpo dei `MessageTemplate` in un
iframe `sandbox=""`, mai in `v-html` — e sanitizzando a monte la si rispetta
senza chiudere il testo in un iframe, che in mezzo a una pagina sarebbe
scomodo.

Il testo sta nella voce, non nel documento: due link possono avere
chiarimenti diversi sugli stessi allegati.

Estensione possibile, non nel primo giro: segnaposto `{{quota_condominio}}`
risolti alla generazione, come già fa il generatore documenti. Per ora il
valore lo scrivi tu, e resta quello che era il giorno in cui hai mandato il
link — che per un chiarimento è probabilmente giusto.

---

# Parte 3 — Il modello

Su `PropertyDocument`, due campi nuovi:

```python
copia_di = FK("self", PROTECT, null=True, blank=True,
              related_name="copie_lettura",
              verbose_name="copia per la lettura di",
              help_text="Versione priva dei dati personali di terzi. "
                        "Non compare fra i documenti ufficiali.")
esponibile = BooleanField(default=False,
              verbose_name="esponibile in un link di lettura")
```

`PROTECT` e non `SET_NULL`, come diceva la prima stesura: azzerando
`copia_di` — eliminando l'originale — la copia oscurata resterebbe in
tabella **senza più il marchio di copia**, e finirebbe in «Altri documenti»
e, se visibile agli inquilini, nella loro pagina. È l'esito esatto che il
campo esiste per impedire. Eliminare un originale che ha copie ora dà 409
con l'elenco di cosa lo trattiene.

`properties/models/share.py`:

```python
def genera_token():
    return secrets.token_urlsafe(32)


class DocumentShare(TimestampedModel):
    property      = FK(Property, related_name="link_documenti")
    token         = CharField(64, unique=True, default=genera_token)
    destinatario  = CharField(120)          # "Simona Bagnato", testo libero
    tenant        = FK(TenantProfile, null=True, blank=True)
    introduzione  = TextField(blank=True)   # due righe in cima
    attivo        = BooleanField(default=True)      # revoca
    visite        = PositiveIntegerField(default=0)
    ultima_visita = DateTimeField(null=True, blank=True)
    creato_da     = FK(User, SET_NULL, null=True)


class ShareItem(TimestampedModel):
    share      = FK(DocumentShare, CASCADE, related_name="voci")
    ordine     = PositiveIntegerField(default=0)
    titolo     = CharField(160, blank=True)   # vuoto = titolo del documento
    documento  = FK(PropertyDocument, PROTECT, null=True, blank=True)
    corpo_md   = TextField(blank=True)        # se è un chiarimento
    corpo_html = TextField(blank=True, editable=False)  # reso e sanitizzato
```

`PROTECT` sul documento: eliminarne uno che sta in un link deve fermarsi e
dire in quali link sta, non svuotare in silenzio i pacchetti già mandati.

`default=genera_token` è una funzione a livello di modulo:
`default=secrets.token_urlsafe(32)` verrebbe valutato **una volta sola** alla
definizione della classe e ogni riga avrebbe lo stesso token — un link
aprirebbe qualunque pacchetto. E non una lambda: le migration non sanno
serializzarla.

Vincoli in `clean()`:

- una voce ha `documento` **oppure** `corpo_md`, mai entrambi né nessuno;
- il documento della voce è `esponibile` e dello stesso immobile dello share;
- `copia_di`, se valorizzato, punta a un documento dello stesso immobile e
  non è a sua volta una copia.

Niente IP né user-agent nel log: per sapere «l'ha aperto» bastano contatore e
data, e sono dati di un terzo che non serve conservare.

# Parte 4 — Endpoint

Pubblici (`AllowAny`, nessuna sessione):

- `GET /api/v1/public/documenti/<token>/`
  → `{casa, destinatario, introduzione, voci:[{id, titolo, tipo, corpo_html?}]}`
  404 se token sconosciuto o `attivo=False`. Incrementa `visite`.
  Le voci il cui documento non è più `esponibile` **non compaiono**.
- `GET /api/v1/public/documenti/<token>/file/<item_id>/`
  → `FileResponse` **inline**, `X-Robots-Tag: noindex, nofollow`.
  404 se la voce non è di quello share, non ha documento, o il documento non
  è più esponibile.

Gestione (`IsPropertyMember`): `DocumentShareViewSet` + voci (aggiunta,
riordino), `revoca/`; su `property-documents/` l'azione `copia-lettura`
(upload del file oscurato con `copia_di` valorizzato dal server).

Liste della gestione, da filtrare tutte e tre:

| Dove | Filtro |
|---|---|
| chip del contratto | `contract=X`, `copia_di__isnull=True` |
| «Altri documenti» | `contract=None`, `copia_di__isnull=True` |
| «Copie per la lettura» | `copia_di__isnull=False` |
| documenti dell'inquilino (`/i/documenti`) | invariato + `copia_di__isnull=True` |

L'ultima riga è quella da non dimenticare: una copia oscurata non deve
comparire nella pagina di chi ha già l'originale.

**Come è stato fatto**: solo la riga dell'inquilino è un filtro di queryset.
Le altre tre restano client-side — il FE carica i documenti dell'immobile in
una lista sola e la separa sul campo `copia_di`, com'era già per la
distinzione contratto / «Altri documenti». Aggiungere un parametro
`copia_di__isnull` avrebbe voluto dire toccare ogni chiamante esistente per
un filtro che il client fa comunque.

**Serving**: una view sorella di `core/media_private.py`, non un ramo dentro
`_RESOLVERS`. Quella vista ha una dottrina sola — «autorizzazione dal record
che possiede il file, utente autenticato» — e chiude con
`if not request.user.is_authenticated: raise PermissionDenied`. Qui il record
che autorizza è il token: è un'altra vista, e l'invariante dell'altra resta
intatto. I file delle copie restano sotto `documenti-proprieta/` e quindi
restano raggiungibili anche dalla vista autenticata, per i membri: giusto,
sono documenti dell'immobile.

**Mai sotto `media/`**: è servito pubblicamente (dev `static()`, prod
Traefik→Django) e darebbe un link funzionante gratis — enumerabile,
indicizzabile, non revocabile.

# Parte 5 — Frontend

- Route `/d/:token`, `meta.public`, `PublicLayout` (stessa forma di `/g/:slug`).
- `PacchettoDocumenti.vue`: intestazione, voci in ordine, PDF inline, testi nel
  flusso.
- Gestione: sezione «Copie per la lettura» + sezione «Link di lettura» nel tab
  «Contratti e documenti»; compositore con riordino (frecce, come la
  galleria), editor markdown con anteprima, copia link, revoca, «aperto N
  volte».
- Service worker: `/d/:token` **fuori** dalla `navigateFallbackDenylist`
  (rotta SPA), `/api/v1/public/documenti/` **dentro** (backend).

# Parte 6 — Test

- token sconosciuto → 404; link revocato → 404
- voce di un altro share → 404
- documento non più `esponibile` → sparisce dall'elenco e il file dà 404
- una copia per la lettura non compare in nessuna delle liste ufficiali,
  **inclusa** quella dell'inquilino
- eliminare un documento che sta in un link → bloccato, con l'elenco dei link
- header `X-Robots-Tag` presente; anonimo 200 senza sessione
- markdown con `<script>` → non compare nell'HTML reso
- una voce con documento **e** testo → errore di validazione

# Parte 7 — Ordine di lavoro

1. ✅ Backend: `copia_di` + `esponibile`, filtri delle quattro liste, modelli
   share, markdown sanitizzato, endpoint, test.
2. ✅ FE gestione: «Copie per la lettura», compositore, copia link, revoca.
3. ✅ FE pagina pubblica.
4. ⬜ Generatore: variante `anonimo` dell'atto di subentro (`OMISSIS` sui campi
   dell'uscente), che produce direttamente una copia esponibile.
5. ⬜ Dati: caricare le due copie oscurate, spuntare le regole di convivenza,
   comporre il primo pacchetto.

In produzione basta `migrate` (properties `0038`): i due campi nuovi hanno
default, le due tabelle nuove nascono vuote. L'immagine va ricostruita —
`markdown` e `nh3` sono dipendenze nuove.

# Decisioni chiuse

- **Atto di subentro anonimo**: **sì, nel pacchetto**, come anteprima di cosa
  si firmerà. `OMISSIS` sui campi dell'uscente; i dati del destinatario ci
  sono, è lui la controparte. Il PDF generato nasce come copia esponibile,
  legata all'assegnazione per cui è stato prodotto.
- **Oscuramento dei PDF**: **fuori dall'applicazione**. Sandro prepara e
  carica i file già oscurati. Niente comando PyMuPDF: sul contratto reale
  coprirebbe una pagina su sette (le altre sono scansioni senza strato di
  testo) e darebbe una falsa sicurezza sulle altre sei. L'applicazione si
  limita all'avvertenza nel dialog di caricamento.
