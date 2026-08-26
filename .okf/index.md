---
okf_version: "0.1"
---

# Viapal — knowledge bundle

Gestionale PWA per l'affitto a stanze di un appartamento in Via Palestrina (Monza).
Monorepo Django 6 + DRF (backend) e Quasar 2 / Vue 3 (frontend PWA).
Questo bundle cattura la conoscenza **non ricostruibile leggendo il codice**:
algoritmi contabili, invarianti di dominio, decisioni architetturali e playbook operativi.

Partire da qui, poi seguire solo i link rilevanti (progressive disclosure).

# Architettura

* [Architecture overview](architecture/overview.md) - stack, monorepo, deploy, convenzioni.
* [Modello dati](architecture/modello-dati.md) - mappa Receivable-centrica delle entità.
* [Auth e ruoli](architecture/auth-e-ruoli.md) - sessione Django, gruppi, inviti, impersonation.
* [PWA](architecture/pwa.md) - service worker, Web Push, reload post-deploy.

# Dominio (logica contabile)

* [Receivable](domain/receivable.md) - l'addebito unificato, cuore del modello.
* [Riconciliazione bonifici](domain/riconciliazione.md) - matching BT↔Receivable, allocations M:N, invarianti.
* [Generazione affitti](domain/generazione-affitti.md) - canoni mensili, pro-rata, quota condominio.
* [Calcolo utenze](domain/calcolo-utenze.md) - bolletta→periodo, pro-rata giorni, pinning, invio avvisi.
* [Conguaglio](domain/conguaglio.md) - conguaglio periodico e previsionale.
* [Deposito](domain/deposito.md) - versamento e restituzione cauzionale.
* [Saldi proprietari](domain/saldi-proprietari.md) - contabilità inter-proprietario e settlement.
* [Conto economico](domain/conto-economico.md) - cassa vs competenza e il ponte tra i due.
* [Solleciti e registro comunicazioni](domain/solleciti.md) - riepilogo addebiti (canone del mese + pendenti a 15 giorni), niente totali né QR, registro degli invii.
* [Link di lettura dei documenti](domain/link-lettura.md) - pacchetto a token per chi deve ancora firmare; `copia_di` + `esponibile`, revoca a grana fine.
* [Galleria pubblica](domain/galleria-pubblica.md) - annuncio affitto /g/slug, editing in-place, endpoint AllowAny.
* [Fascicolo documenti](domain/fascicolo-documenti.md) - checklist documenti inquilino, stati derivati (scadenza/mancante/a carico proprietà), visore interno.
* [Generazione documenti](domain/generazione-documenti.md) - atto di subentro e cessione di fabbricato in PDF; modello per immobile, dati mancanti con il posto in cui compilarli.
* [Unità intera](domain/unita-intera.md) - Property.tipo_gestione, Room come unità locata, un solo pagatore.
* [Conti bancari per immobile](domain/conti-per-immobile.md) - il conto è unico, ma dove è in uso è esplicito: su questo poggia l'isolamento dei movimenti.

# Decisioni e invarianti

* [decisions/](decisions/) - unificazione Receivable, "banca vince sempre", guardia allocations, segni concordi, allocazioni non eccedenti.

# Reference modelli Django

* [models/](models/) - reference strutturale (campi, FK) per app: properties, billing, accounting, accounts, notifications.

# Playbook

* [playbooks/](playbooks/) - dev setup, validazione, import dati storici.
