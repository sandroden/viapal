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
* [Saldi fratelli](domain/saldi-fratelli.md) - contabilità inter-proprietario e settlement.
* [Conto economico](domain/conto-economico.md) - cassa vs competenza e il ponte tra i due.
* [Galleria pubblica](domain/galleria-pubblica.md) - annuncio affitto /g/slug, editing in-place, endpoint AllowAny.

# Decisioni e invarianti

* [decisions/](decisions/) - unificazione Receivable, "banca vince sempre", guardia allocations, segni concordi.

# Reference modelli Django

* [models/](models/) - reference strutturale (campi, FK) per app: properties, billing, accounting, accounts, notifications.

# Playbook

* [playbooks/](playbooks/) - dev setup, validazione, import dati storici.
