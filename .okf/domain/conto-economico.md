---
type: Domain Logic
title: Conto economico (cassa vs competenza)
description: Le due viste contabili e il ponte tra conguaglio di cassa e saldi live.
resource: backend/apps/accounting/
tags: [domain, conto-economico, cassa, competenza]
timestamp: 2026-07-08T00:00:00Z
---

# Overview

Il conto economico per i proprietari esiste in due letture:

- **Cassa**: cosa è effettivamente entrato/uscito (movimenti bancari).
- **Competenza**: cosa è di competenza del periodo, a prescindere dall'incasso.

Frontend: `/p/conto-economico` (`ProprietarioContoEconomico.vue`).

# Il ponte competenza ↔ cassa

Per i fratelli serve riconciliare le due viste. Relazione chiave individuata:

```
conguaglio_cassa = − saldi_live.totale
```

Cioè il conguaglio di cassa è l'opposto del totale dei [saldi live](/domain/saldi-fratelli.md).
La scelta di design è stata **non** creare una terza pagina dedicata, ma un box
dentro `ContoEconomico` con deep-link a `SaldiFratelli`.

# Nota aperta

Esiste un mismatch noto **anno-vs-live** (P0): la vista per anno e quella live
possono divergere; da tenere presente quando i numeri non tornano.

# Vedi anche

- [Saldi fratelli](/domain/saldi-fratelli.md), [Conguaglio](/domain/conguaglio.md).
