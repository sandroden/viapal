# Registro delle attività di trattamento

*Documento interno (artt. 30.1 e 30.2 GDPR). Da tenere aggiornato: rivedere
a ogni nuova funzionalità che tocca dati personali e a ogni nuovo
proprietario accreditato. Non va firmato né pubblicato; va esibito solo su
richiesta del Garante.*

Ultimo aggiornamento: {{data}}

## Sezione A — Trattamenti come titolare

Titolare: Sandro Dentella (con i contitolari {{comproprietari}} per gli
immobili in comproprietà), e-mail sandro.dentella@gmail.com.

### A.1 Gestione locazioni dei propri immobili

| Voce | Contenuto |
|---|---|
| Finalità | Gestione contratti di locazione: anagrafiche, canoni, utenze, depositi, riconciliazione bancaria, documenti, comunicazioni |
| Basi giuridiche | Contratto (6.1.b); obblighi legali fiscali e di PS (6.1.c); legittimo interesse (6.1.f) per tutela dei diritti |
| Categorie di interessati | Inquilini attuali e passati; candidati inquilini |
| Categorie di dati | Anagrafici (nome, cognome, **luogo e data di nascita, cittadinanza, residenza**), contatto, CF, **estremi del documento d'identità** (tipo, numero, autorità e data di rilascio), copie documenti d'identità e permessi di soggiorno, documentazione reddituale, dati contabili e bancari (bonifici, IBAN ordinante), credenziali, log |
| Destinatari | Agenzia delle Entrate, autorità PS (obblighi di legge); fornitori tecnici (v. sotto) |
| Trasferimenti extra-UE | Nessuno |
| Conservazione | V. informativa inquilini: contratti/contabilità 10 anni; documenti identità durata rapporto + 5 anni; reddituale max 12 mesi dalla firma |
| Misure di sicurezza | V. Allegato B dell'accordo art. 28 (HTTPS, autenticazione, media protetti, backup, separazione per membership) |

### A.1.1 Registro delle comunicazioni inviate agli inquilini

| Voce | Contenuto |
|---|---|
| Finalità | Prova di cosa è stato comunicato all'inquilino (avvisi utenze, riepiloghi addebiti, inviti) e diagnosi degli invii falliti |
| Base giuridica | Contratto (6.1.b) per le comunicazioni contrattuali; legittimo interesse (6.1.f) per la tracciabilità degli invii |
| Interessati | Inquilini attuali e passati |
| Dati | Indirizzo e-mail effettivo di recapito (può essere l'e-mail alternativa) o etichetta del dispositivo per le notifiche push; oggetto e **corpo integrale** del messaggio, che riporta importi e scadenze degli addebiti; data di invio; eventuale messaggio d'errore |
| Dove | Tabella `notifications_notification`; consultabile da `/p/riepilogo` (tab *Inviati*), dalla scheda inquilino e dall'admin |
| Conservazione | **Da definire**: oggi nessuna cancellazione automatica. Valutare una purge oltre i 24 mesi, separata dalla conservazione decennale della contabilità (qui il dato utile è la prova dell'invio, non l'importo) |

### A.1.2 Documenti generati (atto di subentro, cessione di fabbricato)

| Voce | Contenuto |
|---|---|
| Finalità | Produrre l'atto di subentro nel contratto di locazione e la comunicazione di cessione di fabbricato (art. 12 D.L. 59/1978) dai dati già in archivio, invece di ricopiarli a mano |
| Basi giuridiche | Contratto (6.1.b) per l'atto di subentro; obbligo legale (6.1.c) per la comunicazione all'autorità di PS |
| Interessati | Inquilini entranti e uscenti; **proprietari** (compaiono come parte locatrice e come cedente) |
| Dati | Nascita, cittadinanza e residenza di inquilini e proprietari; estremi del documento d'identità del cessionario; estremi di registrazione del contratto; canone, oneri accessori e deposito |
| Nota sul flusso | Il PDF prodotto è un documento dell'inquilino ed è **visibile all'inquilino stesso**: la comunicazione di cessione porta quindi nascita, residenza e recapito del proprietario firmatario alla conoscenza dell'inquilino. È inerente al modulo, che quei dati li espone per legge, ma è un flusso proprietario → inquilino che prima non esisteva |
| Dove | `properties_tenantdocument` con `generato=True`, su storage privato (`/media-private/`); modelli in `properties_documenttemplate` |
| Minimizzazione | I campi anagrafici estesi si compilano **solo quando serve un documento**: fuori da questo trattamento restano vuoti. Dopo la consegna all'ufficio, gli estremi del documento d'identità possono essere cancellati |
| Conservazione | Come i documenti contrattuali (v. A.1); l'atto di subentro segue il contratto a cui accede |

### A.2 Account dei proprietari accreditati

| Voce | Contenuto |
|---|---|
| Finalità | Erogazione della piattaforma ai proprietari accreditati |
| Base giuridica | Contratto/condizioni d'uso (6.1.b) |
| Interessati | Proprietari accreditati |
| Dati | Anagrafica, contatti, credenziali, coordinate bancarie immobili, log |
| Conservazione | Durata account + 12 mesi |

## Sezione B — Trattamenti come responsabile (art. 30.2)

Responsabile: Sandro Dentella. Per ciascun titolare-cliente:

| Titolare | Accordo art. 28 | Categorie di trattamenti | Sub-responsabili | Note |
|---|---|---|---|---|
| {{nome_moglie}} | firmato il {{data_firma}} | Hosting e gestione applicativa dati locazioni (come Allegato A dell'accordo) | Contabo GmbH (hosting, DE); {{smtp}} (e-mail) | |

*(aggiungere una riga per ogni nuovo proprietario accreditato)*

## Fornitori / sub-responsabili

| Fornitore | Ruolo | Sede | Garanzia |
|---|---|---|---|
| Contabo GmbH | Hosting VPS | Monaco, Germania (UE) | DPA art. 28 concluso via Customer Control Panel il {{data_dpa_contabo}} |
| {{fornitore_smtp}} | Invio e-mail | {{sede}} | {{estremi_dpa}} |
