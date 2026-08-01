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
| Categorie di dati | Anagrafici, contatto, CF, copie documenti d'identità e permessi di soggiorno, documentazione reddituale, dati contabili e bancari (bonifici, IBAN ordinante), credenziali, log |
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
